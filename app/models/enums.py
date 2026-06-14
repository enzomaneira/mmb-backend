import enum


class ProductType(str, enum.Enum):
    FELT = "FELT"
    CLOTH = "CLOTH"
    CHRISTMAS = "CHRISTMAS"
    SCHOOL = "SCHOOL"
    DECORATION = "DECORATION"
    KEEPSAKE = "KEEPSAKE"
    COSTUME = "COSTUME"
    EASTER = "EASTER"
    PUPPETS = "PUPPETS"
    MISC = "MISC"
    REPAIR = "REPAIR"
    QUIET_BOOK = "QUIET_BOOK"
    TOYS = "TOYS"
    STATIONERY = "STATIONERY"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    DELIVERED = "DELIVERED"
    PAID = "PAID"
    CANCELED = "CANCELED"
