from enum import Enum

class LabelMode(Enum):
    DragMode = 0
    # DefaultMode = DragMode
    DefaultMode = 0
    PointMode = 1
    LineMode = 2
    AngleMode = 3
    CircleMode = 4
    MidpointMode = 5
    VerticalMode = 6
