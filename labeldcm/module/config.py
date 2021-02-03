class Config(object):
    def __init__(self):
        # Font Size
        # 1. Index, Distance, Degree
        self.fontSize = 10

        # Font Family
        # 1. Index, Distance, Degree
        self.fontFamily = 'Consolas'

        # Shifting
        # 1. Index
        self.indexShifting = 3
        # 2. Distance
        self.distanceShifting = 8
        # 3. Degree
        self.degreeShiftingBase = 15
        self.degreeShiftingMore = 30

        # Width
        # 1. Point
        self.pointWidth = 7
        # 2. Line, Circle
        self.lineWidth = 3
        # 3. Angle
        self.angleWidth = 2

        # Color
        # 1. Default
        self.defaultColor = 'red'
        # 2. List
        self.colorList = [
            'red',
            'green',
            'blue',
            'cyan',
            'yellow',
            'black',
            'white',
            'gray'
        ]

        # Ratio
        # 1. Angle
        # For ∠ABC, the radius of the degree is
        # r = min(AB, AC) * ratioToRadius
        self.ratioToRadius = 0.2

        # Math Constant
        self.eps = 1e-5
        self.base = 2 ** 7

        # Debug
        self.debug = True

        # 操作列表
        self.defaultAction = '无操作'
        self.actionList = ['无操作', '点', '线', '角度', '圆', '中点', '直角', '移动点', '删除点']

    def __setattr__(self, key, value):
        if key in self.__dict__:
            raise self.ConstException
        self.__dict__[key] = value

    def __getattr__(self, item):
        if item in self.__dict__:
            return self.item
        raise self.ScopeException

config = Config()
