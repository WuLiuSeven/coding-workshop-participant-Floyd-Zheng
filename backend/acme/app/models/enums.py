from enum import Enum

# used in user.py
class Role(str, Enum):
    EMPLOYEE = "Employee"
    FACILITY_ADMIN = "Facility_Admin"
    ENGINEER = "Engineer"

# used in incident.py
class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

# used in incident.py
class Status(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In-Progress"
    BLOCKED = "Blocked"
    RESOLVED = "Resolved"
    CLOSED = "Closed"

# used in incident.py
class Category(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    EQUIPMENT = "Equipment"
    SECURITY = "Security"
    HARDWARE = "Hardware"
    SOFTWARE = "Software"
    OTHER = "Other"

class Team(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    EQUIPMENT = "Equipment"
    SECURITY = "Security"
    HARDWARE = "Hardware"
    SOFTWARE = "Software"
