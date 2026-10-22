// Incident analytics: status pie chart + time-to-acknowledge / time-to-complete diagnostics.
// Pure SVG + MUI, no extra chart library needed.
import { useMemo, useState } from 'react';
import { Box, Card, CardContent, Divider, Stack, Tooltip, Typography, useTheme } from '@mui/material';

// ---------------------------------------------------------------------------
// Classification (shared with LocationsDataGrid)
// ---------------------------------------------------------------------------
export const INCIDENT_STATES = [
    { key: 'reported', label: 'Reported', paletteKey: 'warning', hint: 'Waiting for someone to pick it up' },
    { key: 'in_progress', label: 'In progress', paletteKey: 'info', hint: 'Acknowledged, being worked on' },
    { key: 'completed', label: 'Completed', paletteKey: 'success', hint: 'Resolved or closed' },
];

const norm = (s) => String(s ?? '').toLowerCase();

export function classifyIncident(incident) {
    const status = norm(incident.status);
    if (incident.resolved_at || status === 'resolved' || status === 'closed') return 'completed';
    if (incident.acknowledged_at || status === 'in_progress' || status === 'blocked') return 'in_progress';
    return 'reported';
}

export const stateLabel = (key) => INCIDENT_STATES.find((s) => s.key === key)?.label ?? key;

// ---------------------------------------------------------------------------
// Duration helpers
// ---------------------------------------------------------------------------
const toMs = (value) => (value ? new Date(value).getTime() : NaN);

function durationsBetween(incidents, fromField, toField) {
    const out = [];
    for (const inc of incidents) {
        const ms = toMs(inc[toField]) - toMs(inc[fromField]);
        if (Number.isFinite(ms) && ms >= 0) out.push(ms);
    }
    return out.sort((a, b) => a - b);
}

function summarize(sorted) {
    if (sorted.length === 0) return null;
    const mid = Math.floor(sorted.length / 2);
    const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    const average = sorted.reduce((a, b) => a + b, 0) / sorted.length;
    return { count: sorted.length, median, average, fastest: sorted[0], slowest: sorted[sorted.length - 1] };
}

export function formatDuration(ms) {
    if (ms == null || !Number.isFinite(ms)) return '–';
    const minutes = Math.round(ms / 60000);
    if (minutes < 1) return '< 1m';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ${minutes % 60}m`;
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
}

// ---------------------------------------------------------------------------
// Pie chart (SVG donut)
// ---------------------------------------------------------------------------
function arcPath(cx, cy, r, start, end) {
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + r * Math.sin(start), y1 = cy - r * Math.cos(start);
    const x2 = cx + r * Math.sin(end), y2 = cy - r * Math.cos(end);
    return `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2} Z`;
}

function StatusPie({ slices, total, onSelect }) {
    const theme = useTheme();
    const [hovered, setHovered] = useState(null);
    const size = 200, c = size / 2, r = 92, hole = 56;

    let angle = 0;
    const arcs = slices.filter((s) => s.value > 0).map((s) => {
        const sweep = (s.value / total) * Math.PI * 2;
        const arc = { ...s, start: angle, end: angle + sweep };
        angle += sweep;
        return arc;
    });

    const focus = slices.find((s) => s.key === hovered);

    return (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={3} alignItems="center">
            <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img"
                 aria-label="Incidents by status">
                {total === 0 && <circle cx={c} cy={c} r={r} fill={theme.palette.action.disabledBackground} />}
                {arcs.map((a) => {
                    const fill = theme.palette[a.paletteKey].main;
                    const common = {
                        fill,
                        stroke: theme.palette.background.paper,
                        strokeWidth: 2,
                        opacity: hovered && hovered !== a.key ? 0.45 : 1,
                        style: { cursor: onSelect ? 'pointer' : 'default', transition: 'opacity 120ms' },
                        onMouseEnter: () => setHovered(a.key),
                        onMouseLeave: () => setHovered(null),
                        onClick: () => onSelect?.(a.key),
                    };
                    return arcs.length === 1
                        ? <circle key={a.key} cx={c} cy={c} r={r} {...common}><title>{a.label}: {a.value}</title></circle>
                        : <path key={a.key} d={arcPath(c, c, r, a.start, a.end)} {...common}><title>{a.label}: {a.value}</title></path>;
                })}
                <circle cx={c} cy={c} r={hole} fill={theme.palette.background.paper} pointerEvents="none" />
                <text x={c} y={c - 4} textAnchor="middle" fontSize="28" fontWeight="600"
                      fill={theme.palette.text.primary} pointerEvents="none">
                    {focus ? focus.value : total}
                </text>
                <text x={c} y={c + 18} textAnchor="middle" fontSize="12"
                      fill={theme.palette.text.secondary} pointerEvents="none">
                    {focus ? focus.label : 'incidents'}
                </text>
            </svg>

            <Stack spacing={1} sx={{ minWidth: 180 }}>
                {slices.map((s) => {
                    const pct = total ? Math.round((s.value / total) * 100) : 0;
                    return (
                        <Tooltip key={s.key} arrow placement="right"
                                 title={onSelect ? `${s.hint}. Click to view these incidents.` : s.hint}>
                            <Stack direction="row" spacing={1} alignItems="center"
                                   onMouseEnter={() => setHovered(s.key)}
                                   onMouseLeave={() => setHovered(null)}
                                   onClick={() => onSelect?.(s.key)}
                                   sx={{
                                       cursor: onSelect ? 'pointer' : 'default', px: 1, py: 0.5, borderRadius: 1,
                                       bgcolor: hovered === s.key ? 'action.hover' : 'transparent',
                                   }}>
                                <Box sx={{ width: 12, height: 12, borderRadius: '3px', bgcolor: `${s.paletteKey}.main` }} />
                                <Typography variant="body2" sx={{ flex: 1 }}>{s.label}</Typography>
                                <Typography variant="body2" fontWeight={600}>{s.value}</Typography>
                                <Typography variant="caption" color="text.secondary" sx={{ width: 36, textAlign: 'right' }}>
                                    {pct}%
                                </Typography>
                            </Stack>
                        </Tooltip>
                    );
                })}
            </Stack>
        </Stack>
    );
}

// ---------------------------------------------------------------------------
// Duration diagnostic card
// ---------------------------------------------------------------------------
function DurationCard({ title, description, stats, waiting }) {
    return (
        <Card variant="outlined" sx={{ flex: 1, minWidth: 240 }}>
            <CardContent>
                <Tooltip arrow title={description} placement="top-start">
                    <Typography variant="subtitle2" color="text.secondary" sx={{ cursor: 'help', width: 'fit-content' }}>
                        {title}
                    </Typography>
                </Tooltip>

                <Typography variant="h4" sx={{ mt: 1, fontWeight: 600 }}>
                    {formatDuration(stats?.median)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    median{stats ? ` across ${stats.count} incident${stats.count === 1 ? '' : 's'}` : ' (no data yet)'}
                </Typography>

                <Divider sx={{ my: 1.5 }} />

                <Stack direction="row" justifyContent="space-between">
                    {[
                        ['Average', stats?.average],
                        ['Fastest', stats?.fastest],
                        ['Slowest', stats?.slowest],
                    ].map(([label, value]) => (
                        <Box key={label}>
                            <Typography variant="caption" color="text.secondary">{label}</Typography>
                            <Typography variant="body2" fontWeight={500}>{formatDuration(value)}</Typography>
                        </Box>
                    ))}
                </Stack>

                {waiting.count > 0 && (
                    <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 1.5 }}>
                        {waiting.count} still waiting · oldest {formatDuration(waiting.oldest)}
                    </Typography>
                )}
            </CardContent>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------
export default function IncidentAnalytics({ incidents, onSelectState }) {
    const analytics = useMemo(() => {
        const now = Date.now();
        const counts = { reported: 0, in_progress: 0, completed: 0 };
        const waitingAck = { count: 0, oldest: 0 };
        const waitingResolve = { count: 0, oldest: 0 };

        for (const inc of incidents) {
            const state = classifyIncident(inc);
            counts[state] += 1;
            if (state === 'reported' && inc.created_at) {
                waitingAck.count += 1;
                waitingAck.oldest = Math.max(waitingAck.oldest, now - toMs(inc.created_at));
            }
            if (state === 'in_progress' && inc.acknowledged_at) {
                waitingResolve.count += 1;
                waitingResolve.oldest = Math.max(waitingResolve.oldest, now - toMs(inc.acknowledged_at));
            }
        }

        return {
            slices: INCIDENT_STATES.map((s) => ({ ...s, value: counts[s.key] })),
            total: incidents.length,
            ack: summarize(durationsBetween(incidents, 'created_at', 'acknowledged_at')),
            resolve: summarize(durationsBetween(incidents, 'acknowledged_at', 'resolved_at')),
            waitingAck,
            waitingResolve,
        };
    }, [incidents]);

    return (
        <Stack direction={{ xs: 'column', lg: 'row' }} spacing={2} sx={{ mb: 3 }}>
            <Card variant="outlined" sx={{ flex: 1.4 }}>
                <CardContent>
                    <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                        Incidents by status
                    </Typography>
                    <StatusPie slices={analytics.slices} total={analytics.total} onSelect={onSelectState} />
                </CardContent>
            </Card>

            <DurationCard
                title="Time to acknowledge"
                description="From when an incident is reported (created_at) to when someone acknowledges it (acknowledged_at)"
                stats={analytics.ack}
                waiting={analytics.waitingAck}
            />

            <DurationCard
                title="Time to complete"
                description="From when an incident is acknowledged (acknowledged_at) to when it is resolved (resolved_at)"
                stats={analytics.resolve}
                waiting={analytics.waitingResolve}
            />
        </Stack>
    );
}
