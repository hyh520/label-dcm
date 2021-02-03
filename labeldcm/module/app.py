from labeldcm.module import static
from labeldcm.module.config import config
from labeldcm.module.mode import LabelMode
from labeldcm.ui.form import Ui_Form
from PyQt5.QtCore import pyqtBoundSignal, QCoreApplication, QEvent, QObject, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QResizeEvent
from PyQt5.QtWidgets import QAction, QFileDialog, QGraphicsScene, QInputDialog, \
    QMainWindow, QMenu, QMessageBox, QStatusBar
from typing import Dict, Optional, Set, Tuple

class LabelApp(QMainWindow, Ui_Form):
    def __init__(self):
        super(LabelApp, self).__init__()
        self.setupUi(self)
        self.retranslateUi(self)

        # qss设置
        with open('labeldcm/assets/style.qss', 'r', encoding='utf-8') as f:
            self.setStyleSheet(f.read())

        # 初始化颜色单选框
        self.initColorBox()
        self.color = QColor(config.defaultColor)

        # 初始化操作单选框
        self.initActionBox()
        self.mode = LabelMode.DefaultMode

        # 图片比例，初始100%
        self.imgSize = 1

        # 初始化画布，原图，现图，现图/原图，原图/现图
        self.src: Optional[QPixmap] = None
        self.img: Optional[QPixmap] = None
        self.ratioFromOld = 1
        self.ratioToSrc = 1

        self.targetEventType = [QMouseEvent.MouseButtonPress, QMouseEvent.MouseMove, QMouseEvent.MouseButtonRelease]
        self.initEventConnections()

        # Init Index
        self.indexA = -1
        self.indexB = -1
        self.indexC = -1

        # A: IndexA - A, Color
        self.points: Dict[int, Tuple[QPointF, QColor]] = {}

        # AB: IndexA, IndexB - Color
        self.lines: Dict[Tuple[int, int], QColor] = {}

        # ∠ABC: IndexA, IndexB, IndexC - Color
        self.angles: Dict[Tuple[int, int, int], QColor] = {}

        # ⊙A, r = AB: IndexA, IndexB - Color
        self.circles: Dict[Tuple[int, int], QColor] = {}

        # Init Pivots
        self.pivots: Set[int] = set()

        # Init Highlight 选中的点
        self.highlightMoveIndex = -1
        self.highlightPoints: Set[int] = set()

        # Init Right Button Menu
        self.rightBtnMenu = QMenu(self)

        # 状态栏
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)

    # 绑定事件
    def initEventConnections(self):
        self.imgView.viewport().installEventFilter(self)
        self.loadImgBtn.triggered.connect(self.uploadImg)
        self.storeImgBtn.triggered.connect(self.saveImg)
        self.colorBox.currentIndexChanged.connect(self.changeColor)
        self.actionBox.currentIndexChanged.connect(self.changeMode)
        self.imgSizeSlider.valueChanged.connect(self.changeImgSizeSlider)
        self.clearAllBtn.triggered.connect(self.initImgWithPoints)
        self.deleteImgBtn.triggered.connect(self.clearImg)
        self.addSizeBtn.triggered.connect(self.addImgSize)
        self.subSizeBtn.triggered.connect(self.subImgSize)
        self.originalSizeBtn.triggered.connect(self.originalImgSize)
        self.quitAppBtn.triggered.connect(QCoreApplication.instance().quit)
        self.aiBtn.triggered.connect(self.aiPoint)

    # 更新关键点信息
    def updatePivotsInfo(self):
        if not self.img or not self.points or not self.pivots:
            self.pivotsInfo.setMarkdown('')
            return None
        pivots = list(self.pivots)
        pivots.sort()
        mdInfo = ''
        for index in pivots:
            point = self.getSrcPoint(self.points[index][0])
            mdInfo += '{}: ({}, {})\n\n'.format(index, round(point.x(), 2), round(point.y(), 2))
        self.pivotsInfo.setMarkdown(mdInfo)

    # 初始化画布
    def initImg(self):
        self.src = None
        self.img = None
        self.ratioFromOld = 1
        self.ratioToSrc = 1
        self.patientInfo.setMarkdown('')

    # 更新图片,依据画布尺寸自动更新图片尺寸
    def updateImg(self):
        if not self.src:
            self.initImg()
            return None
        old = self.img if self.img else self.src
        size = QSize(
            (self.imgView.width() - 2 * self.imgView.lineWidth()) * self.imgSize,
            (self.imgView.height() - 2 * self.imgView.lineWidth()) * self.imgSize
        )
        self.img = self.src.scaled(size, Qt.KeepAspectRatio)
        self.ratioFromOld = self.img.width() / old.width()
        self.ratioToSrc = self.src.width() / self.img.width()

    # 更新画布,添加图片到画布
    def updateImgView(self):
        scene = QGraphicsScene()
        if self.img:
            scene.addPixmap(self.img)
        self.imgView.setScene(scene)

    # DICOM (*.dcm),得到dicom文件的pixmap和内含信息
    def loadDcmImg(self, imgDir: str):
        if static.isImgAccess(imgDir):
            self.src, mdInfo = static.getDcmImgAndMdInfo(imgDir)
            self.patientInfo.setMarkdown(mdInfo)
            self.updateAll()
        else:
            self.warning('The image file is not found or unreadable!')

    # JPEG (*.jpg;*.jpeg;*.jpe), PNG (*.png)
    def loadImg(self, imgDir: str):
        if static.isImgAccess(imgDir):
            self.src = QPixmap()
            self.src.load(imgDir)
            self.updateAll()
        else:
            self.warning('The image file is not found or unreadable!')

    # 上传图片到画布
    def uploadImg(self):
        caption = 'Open Image File'
        extFilter = 'DICOM (*.dcm);;JPEG (*.jpg;*.jpeg;*.jpe);;PNG (*.png)'
        dcmFilter = 'DICOM (*.dcm)'
        imgDir, imgExt = QFileDialog.getOpenFileName(self, caption, static.getHomeImgDir(), extFilter, dcmFilter)
        if not imgDir:
            return None
        self.initAll()
        if imgExt == dcmFilter:
            self.loadDcmImg(imgDir)
        else:
            self.loadImg(imgDir)

    # 保存结果
    def saveImg(self):
        if not self.src:
            self.warning('Please upload an image file first!')
        img = self.src.copy()
        self.eraseHighlight()
        self.updateLabels(img, True)
        caption = 'Save Image File'
        extFilter = 'JPEG (*.jpg;*.jpeg;*.jpe);;PNG (*.png)'
        initFilter = 'JPEG (*.jpg;*.jpeg;*.jpe)'
        imgDir, _ = QFileDialog.getSaveFileName(self, caption, static.getHomeImgDir(), extFilter, initFilter)
        if imgDir:
            img.save(imgDir)

    # 初始化颜色单选框
    def initColorBox(self):
        size = self.colorBox.iconSize()
        index = 0
        defaultIndex = -1
        for color in config.colorList:
            if color == config.defaultColor:
                defaultIndex = index
            colorIcon = QPixmap(size)
            colorIcon.fill(QColor(color))
            self.colorBox.addItem(QIcon(colorIcon), f'  {color.capitalize()}')
            index += 1
        self.colorBox.setCurrentIndex(defaultIndex)

    # 初始化操作单选框
    def initActionBox(self):
        index = 0
        defaultIndex = -1
        for action in config.actionList:
            if action == config.defaultAction:
                defaultIndex = index
            self.actionBox.addItem(f'    {action}')
            index += 1
        self.actionBox.setCurrentIndex(defaultIndex)

    # 改变滑块
    def changeImgSizeSlider(self):
        size = self.imgSizeSlider.value()
        self.imgSize = size / 100
        self.imgSizeLabel.setText(f'大小：{size}%')
        self.updateAll()

    def addImgSize(self):
        size = min(int(self.imgSize * 100 + 10), 200)
        self.imgSizeSlider.setValue(size)
        self.imgSize = size / 100
        self.imgSizeLabel.setText(f'大小：{size}%')
        self.updateAll()

    def subImgSize(self):
        size = max(int(self.imgSize * 100 - 10), 50)
        self.imgSizeSlider.setValue(size)
        self.imgSize = size / 100
        self.imgSizeLabel.setText(f'大小：{size}%')
        self.updateAll()

    def originalImgSize(self):
        size = 100
        self.imgSizeSlider.setValue(size)
        self.imgSize = size / 100
        self.imgSizeLabel.setText(f'大小：{size}%')
        self.updateAll()

    # 改变颜色
    def changeColor(self):
        self.color = QColor(config.colorList[self.colorBox.currentIndex()])

    # 改变状态
    def changeMode(self):
        self.eraseHighlight()
        text = config.actionList[self.actionBox.currentIndex()]
        mode: LabelMode
        if text == '点':
            mode = LabelMode.PointMode
        elif text == '线':
            mode = LabelMode.LineMode
        elif text == '角度':
            mode = LabelMode.AngleMode
        elif text == '圆':
            mode = LabelMode.CircleMode
        elif text == '中点':
            mode = LabelMode.MidpointMode
        elif text == '直角':
            mode = LabelMode.VerticalMode
        elif text == '移动点':
            mode = LabelMode.MovePointMode
        elif text == '删除点':
            mode = LabelMode.ClearPointMode
        else:
            mode = LabelMode.DefaultMode
        self.mode = mode

    def initIndex(self):
        self.indexA = -1
        self.indexB = -1
        self.indexC = -1

    def initHighlight(self):
        self.highlightMoveIndex = -1
        self.highlightPoints.clear()

    # 清除点，线，角度，圆，中点，高
    def initExceptImg(self):
        self.initIndex()
        self.points.clear()
        self.lines.clear()
        self.angles.clear()
        self.circles.clear()
        self.pivots.clear()
        self.initHighlight()

    # 更新点位置
    def updatePoints(self):
        if not self.img or not self.points or self.ratioFromOld == 1:
            return None
        for point, _ in self.points.values():
            point.setX(point.x() * self.ratioFromOld)
            point.setY(point.y() * self.ratioFromOld)
        self.ratioFromOld = 1

    # 对应原图点位置
    def getSrcPoint(self, point: QPointF):
        return QPointF(point.x() * self.ratioToSrc, point.y() * self.ratioToSrc)

    # 绘点
    def labelPoints(self, img: Optional[QPixmap], toSrc: bool):
        if not img or not self.points:
            return None
        painter = QPainter()
        painter.begin(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        font = QFont('Consolas')
        if toSrc:
            pen.setWidthF(config.pointWidth * self.ratioToSrc)
            font.setPointSizeF(config.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(config.pointWidth)
            font.setPointSizeF(config.fontSize)
        painter.setFont(font)
        for index, (point, color) in self.points.items():
            labelPoint: QPointF
            if toSrc:
                pen.setColor(color)
                labelPoint = self.getSrcPoint(point)
            else:
                pen.setColor(
                    color if index != self.highlightMoveIndex and index not in self.highlightPoints
                    else QColor.lighter(color)
                )
                labelPoint = point
            painter.setPen(pen)
            painter.drawPoint(labelPoint)
            painter.drawText(static.getIndexShift(labelPoint), str(index))
        painter.end()

    # 绘线
    def labelLines(self, img: Optional[QPixmap], toSrc: bool):
        if not img or not self.lines:
            return None
        painter = QPainter()
        painter.begin(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        font = QFont('Consolas')
        if toSrc:
            pen.setWidthF(config.lineWidth * self.ratioToSrc)
            font.setPointSizeF(config.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(config.lineWidth)
            font.setPointSizeF(config.fontSize)
        painter.setFont(font)
        for (indexA, indexB), color in self.lines.items():
            isHighlight = indexA in self.highlightPoints and indexB in self.highlightPoints \
                and (self.mode == LabelMode.AngleMode or self.mode == LabelMode.VerticalMode)
            pen.setColor(QColor.lighter(color) if isHighlight else color)
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            srcA = self.getSrcPoint(A)
            srcB = self.getSrcPoint(B)
            labelPoint: QPointF
            if toSrc:
                painter.drawLine(srcA, srcB)
                labelPoint = static.getMidpoint(srcA, srcB)
            else:
                painter.drawLine(A, B)
                labelPoint = static.getMidpoint(A, B)
            painter.drawText(static.getDistanceShift(A, B, labelPoint), str(round(static.getDistance(srcA, srcB), 2)))
        painter.end()

    # 绘角度
    def labelAngles(self, img: Optional[QPixmap], toSrc: bool):
        if not img or not self.angles:
            return None
        painter = QPainter()
        painter.begin(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        font = QFont('Consolas')
        if toSrc:
            pen.setWidthF(config.angleWidth * self.ratioToSrc)
            font.setPointSizeF(config.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(config.angleWidth)
            font.setPointSizeF(config.fontSize)
        painter.setFont(font)
        for (indexA, indexB, indexC), color in self.angles.items():
            pen.setColor(color)
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            C = self.points[indexC][0]
            D, E = static.getDiagPoints(self.points[indexA][0], B, C)
            F = static.getArcMidpoint(A, B, C)
            labelRect: QRectF
            labelPointA: QPointF
            labelPointB: QPointF
            if toSrc:
                labelRect = QRectF(self.getSrcPoint(D), self.getSrcPoint(E))
                labelPointA = self.getSrcPoint(B)
                labelPointB = self.getSrcPoint(F)
            else:
                labelRect = QRectF(D, E)
                labelPointA = B
                labelPointB = F
            deg = static.getDegree(A, B, C)
            painter.drawArc(labelRect, int(static.getBeginDegree(A, B, C) * 16), int(deg * 16))
            painter.drawText(static.getDegreeShift(labelPointA, labelPointB), str(round(deg, 2)) + '°')
        painter.end()

    # 绘圆
    def labelCircles(self, img: Optional[QPixmap], toSrc: bool):
        if not img or not self.circles:
            return None
        painter = QPainter()
        painter.begin(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setWidthF(config.lineWidth if not toSrc else config.lineWidth * self.ratioToSrc)
        for (indexA, indexB), color in self.circles.items():
            isHighlight = indexA in self.highlightPoints and indexB in self.highlightPoints \
                and self.mode == LabelMode.CircleMode
            pen.setColor(QColor.lighter(color) if isHighlight else color)
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            painter.drawEllipse(
                static.getMinBoundingRect(A, B) if not toSrc
                else static.getMinBoundingRect(self.getSrcPoint(A), self.getSrcPoint(B))
            )
        painter.end()

    def erasePoint(self, index):
        if index not in self.points:
            return None
        del self.points[index]
        for line in list(self.lines.keys()):
            if index in line:
                del self.lines[line]
        for angle in list(self.angles.keys()):
            if index in angle:
                del self.angles[angle]
        for circle in list(self.circles.keys()):
            if index in circle:
                del self.circles[circle]
        self.pivots.discard(index)

    def eraseHighlight(self):
        if self.mode == LabelMode.CircleMode:
            self.erasePoint(self.indexA)
            self.erasePoint(self.indexB)
        self.initIndex()
        self.initHighlight()
        self.updateAll()

    def updateLabels(self, img: Optional[QPixmap], toSrc: bool):
        self.labelPoints(img, toSrc)
        self.labelLines(img, toSrc)
        self.labelAngles(img, toSrc)
        self.labelCircles(img, toSrc)

    def getImgPoint(self, point: QPointF):
        return QPointF(point.x() / self.ratioToSrc, point.y() / self.ratioToSrc)

    # 更新标号
    def getNewIndex(self):
        return max(self.points.keys() if self.points else [0]) + 1

    # 得到point位置标号
    def getPointIndex(self, point: QPointF):
        if not self.img or not self.points:
            return -1
        distance = config.pointWidth - config.eps
        # Index -1 means the point does not exist
        index = -1
        for idx, (pt, _) in self.points.items():
            dis = static.getDistance(point, pt)
            if dis < distance:
                distance = dis
                index = idx
        return index

    def isPointOutOfBound(self, point: QPointF):
        return point.x() < config.pointWidth / 2 or point.x() > self.img.width() - config.pointWidth / 2 \
            or point.y() < config.pointWidth / 2 or point.y() > self.img.height() - config.pointWidth / 2

    # 得到有效标号数量
    def getIndexCnt(self):
        return len([i for i in [self.indexA, self.indexB, self.indexC] if i != -1])

    # 判断高亮
    def triggerIndex(self, index: int):
        if not self.img or not self.points or index == -1:
            return None
        if index in [self.indexA, self.indexB, self.indexC]:
            indexs = [i for i in [self.indexA, self.indexB, self.indexC] if i != index]
            self.indexA = indexs[0]
            self.indexB = indexs[1]
            self.indexC = -1
            self.highlightPoints.remove(index)
        else:
            indexs = [i for i in [self.indexA, self.indexB, self.indexC] if i != -1]
            indexs.append(index)
            while len(indexs) < 3:
                indexs.append(-1)
            self.indexA = indexs[0]
            self.indexB = indexs[1]
            self.indexC = indexs[2]
            self.highlightPoints.add(index)

    def endTrigger(self):
        self.initIndex()
        self.initHighlight()

    def endTriggerWith(self, index: int):
        self.endTrigger()
        self.highlightMoveIndex = index

    # 添加到各个字典中
    def addPoint(self, point: QPointF):
        if self.img:
            index = self.getNewIndex()
            self.points[index] = point, self.color
            return index

    def addLine(self, indexA: int, indexB: int):
        if self.img and indexA in self.points and indexB in self.points:
            self.lines[static.getLineKey(indexA, indexB)] = self.color

    def addAngle(self, indexA: int, indexB: int, indexC: int):
        if self.img and static.getLineKey(indexA, indexB) in self.lines \
                and static.getLineKey(indexB, indexC) in self.lines:
            self.angles[static.getAngleKey(indexA, indexB, indexC)] = self.color

    def addCircle(self, indexA: int, indexB: int):
        if self.img and indexA in self.points and indexB in self.points:
            self.circles[(indexA, indexB)] = self.color

    # 点击事件
    def handlePointMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        point = self.imgView.mapToScene(evt.pos())
        index = self.getPointIndex(point)
        if index != -1:
            self.points[index] = self.points[index][0], self.color
        else:
            self.addPoint(point)
        self.updateAll()

    def handleLineMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        point = self.imgView.mapToScene(evt.pos())
        index = self.getPointIndex(point)
        if index == -1:
            self.triggerIndex(self.addPoint(point))
        else:
            self.triggerIndex(index)
        if self.getIndexCnt() == 2:
            self.addLine(self.indexA, self.indexB)
            self.endTriggerWith(self.indexB)
        self.updateAll()

    def handleAngleMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        self.triggerIndex(self.getPointIndex(self.imgView.mapToScene(evt.pos())))
        if self.getIndexCnt() == 2 and static.getLineKey(self.indexA, self.indexB) not in self.lines:
            self.triggerIndex(self.indexA)
        elif self.getIndexCnt() == 3:
            if static.getLineKey(self.indexB, self.indexC) in self.lines:
                self.addAngle(self.indexA, self.indexB, self.indexC)
                self.endTriggerWith(self.indexC)
            else:
                indexC = self.indexC
                self.endTrigger()
                self.triggerIndex(indexC)
        self.updateAll()

    def handleCircleMode(self, evt: QMouseEvent):
        point = self.imgView.mapToScene(evt.pos())
        if self.getPointIndex(point) == -1:
            if evt.type() == QMouseEvent.MouseButtonPress:
                if self.getIndexCnt() == 0:
                    self.triggerIndex(self.addPoint(point))
                    self.triggerIndex(
                        self.addPoint(QPointF(point.x() + 2 * config.eps, point.y() + 2 * config.eps))
                    )
                    self.addCircle(self.indexA, self.indexB)
                elif self.getIndexCnt() == 2:
                    self.endTriggerWith(self.indexB)
            elif evt.type() == QMouseEvent.MouseMove and self.getIndexCnt() == 2 and not self.isPointOutOfBound(point):
                self.points[self.indexB][0].setX(point.x())
                self.points[self.indexB][0].setY(point.y())
        else:
            if evt.type() == QMouseEvent.MouseButtonPress:
                if self.getIndexCnt() == 0:
                    self.triggerIndex(self.getPointIndex(point))
                    self.triggerIndex(
                        self.addPoint(QPointF(point.x() + 2 * config.eps, point.y() + 2 * config.eps))
                    )
                    self.addCircle(self.indexA, self.indexB)
                elif self.getIndexCnt() == 2:
                    self.endTriggerWith(self.indexB)
            elif evt.type() == QMouseEvent.MouseMove and self.getIndexCnt() == 2 and not self.isPointOutOfBound(point):
                self.points[self.indexB][0].setX(point.x())
                self.points[self.indexB][0].setY(point.y())
        self.updateAll()

    def handleMidpointMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        self.triggerIndex(self.getPointIndex(self.imgView.mapToScene(evt.pos())))
        if self.getIndexCnt() == 2:
            if static.getLineKey(self.indexA, self.indexB) in self.lines:
                A = self.points[self.indexA][0]
                B = self.points[self.indexB][0]
                indexC = self.addPoint(static.getMidpoint(A, B))
                self.addLine(self.indexA, indexC)
                self.addLine(self.indexB, indexC)
                self.endTriggerWith(self.indexB)
            else:
                self.triggerIndex(self.indexA)
        self.updateAll()

    def handleVerticalMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        self.triggerIndex(self.getPointIndex(self.imgView.mapToScene(evt.pos())))
        if self.getIndexCnt() == 2:
            if static.getLineKey(self.indexA, self.indexB) not in self.lines:
                self.triggerIndex(self.indexA)
        elif self.getIndexCnt() == 3:
            A = self.points[self.indexA][0]
            B = self.points[self.indexB][0]
            C = self.points[self.indexC][0]
            if static.isOnALine(A, B, C):
                if static.getLineKey(self.indexB, self.indexC) in self.lines:
                    self.triggerIndex(self.indexA)
                else:
                    indexC = self.indexC
                    self.endTrigger()
                    self.triggerIndex(indexC)
            else:
                D = static.getFootPoint(A, B, C)
                indexD = self.addPoint(D)
                if not static.isOnSegment(A, B, D):
                    self.addLine(
                        (self.indexA if static.getDistance(A, D) < static.getDistance(B, D) else self.indexB), indexD
                    )
                self.addLine(self.indexC, indexD)
                self.endTriggerWith(self.indexC)
            self.updateAll()

    def handleDragMode(self, evt: QMouseEvent):
        point = self.imgView.mapToScene(evt.pos())
        if evt.type() == QMouseEvent.MouseButtonPress and self.getIndexCnt() == 0:
            self.triggerIndex(self.getPointIndex(point))
        elif evt.type() == QMouseEvent.MouseMove and self.getIndexCnt() == 1 and not self.isPointOutOfBound(point):
            self.points[self.indexA][0].setX(point.x())
            self.points[self.indexA][0].setY(point.y())
        elif evt.type() == QMouseEvent.MouseButtonRelease and self.getIndexCnt() == 1:
            self.triggerIndex(self.indexA)
        self.updateAll()

    def handleClearPointMode(self, evt: QMouseEvent):
        index = self.getPointIndex(self.imgView.mapToScene(evt.pos()))
        if evt.type() == QMouseEvent.MouseButtonPress and index != -1:
            self.erasePoint(index)
        self.updateAll()

    def handleHighlightMove(self, evt: QMouseEvent):
        point = self.imgView.mapToScene(evt.pos())
        self.highlightMoveIndex = self.getPointIndex(point)
        text = f'坐标：{round(point.x(), 2)}, {round(point.y(), 2)}'
        self.statusBar.showMessage(text, 1000)
        self.updateAll()

    def initAll(self):
        self.initImg()
        self.initExceptImg()

    def updateAll(self):
        self.updateImg()
        self.updatePoints()
        self.updateLabels(self.img, False)
        self.updateImgView()
        self.updatePivotsInfo()

    # 清除所有点，还原图片
    def initImgWithPoints(self):
        if not self.img:
            return None
        self.initExceptImg()
        self.updateAll()

    # 清除图片
    def clearImg(self):
        if not self.src:
            return None
        self.initAll()
        self.updateAll()

    # 自动适应窗口
    def resizeEvent(self, _: QResizeEvent):
        self.updateAll()

    # 错误警告
    def warning(self, text: str):
        QMessageBox.warning(self, 'Warning', text)

    # 更改标号
    def modifyIndex(self, index: int):
        newIndex, modify = QInputDialog.getInt(self, '更改标号', '请输入一个新的标号', index, 0, step=1)
        if not modify or newIndex == index:
            return None
        if newIndex <= 0:
            self.warning('标号不可小于或等于0！')
            return None
        if newIndex in self.points:
            self.warning('此标号已存在!')
            return None
        self.points[newIndex] = self.points[index]
        del self.points[index]
        for line in list(self.lines.keys()):
            if index in line:
                fixedIndex = line[0] + line[1] - index
                self.lines[static.getLineKey(newIndex, fixedIndex)] = self.lines[line]
                del self.lines[line]
        for angle in list(self.angles.keys()):
            if index in angle:
                if index == angle[1]:
                    self.angles[angle[0], newIndex, angle[2]] = self.angles[angle]
                else:
                    fixedIndex = angle[0] + angle[2] - index
                    self.angles[static.getAngleKey(newIndex, angle[1], fixedIndex)] = self.angles[angle]
                del self.angles[angle]
        for circle in list(self.circles.keys()):
            if index in circle:
                if index == circle[0]:
                    self.circles[(newIndex, circle[1])] = self.circles[circle]
                else:
                    self.circles[(circle[0], newIndex)] = self.circles[circle]
                del self.circles[circle]
        if index in self.pivots:
            self.pivots.remove(index)
            self.pivots.add(newIndex)

    def addPivots(self, index: int):
        if self.img and index in self.points:
            self.pivots.add(index)

    def removePivots(self, index: int):
        if self.img and self.pivots:
            self.pivots.discard(index)

    def switchPivotState(self, index: int):
        if index not in self.pivots:
            self.addPivots(index)
        else:
            self.removePivots(index)

    def createRightBtnMenu(self, index: int, point: QPointF):
        self.rightBtnMenu = QMenu(self)
        modifyIndex = QAction('更改标号', self.rightBtnMenu)
        modifyIndexTriggered: pyqtBoundSignal = modifyIndex.triggered
        modifyIndexTriggered.connect(lambda: self.modifyIndex(index))
        switchPivotState = QAction('删除该点信息' if index in self.pivots else '查看该点信息', self.rightBtnMenu)
        switchPivotStateTriggered: pyqtBoundSignal = switchPivotState.triggered
        switchPivotStateTriggered.connect(lambda: self.switchPivotState(index))
        erasePoint = QAction('清除该点', self.rightBtnMenu)
        erasePointTriggered: pyqtBoundSignal = erasePoint.triggered
        erasePointTriggered.connect(lambda: self.erasePoint(index))
        self.rightBtnMenu.addAction(modifyIndex)
        self.rightBtnMenu.addAction(switchPivotState)
        self.rightBtnMenu.addAction(erasePoint)
        self.rightBtnMenu.exec(point)

    def handleRightBtnMenu(self, evt: QMouseEvent):
        if (index := self.getPointIndex(self.imgView.mapToScene(evt.pos()))) != -1:
            self.eraseHighlight()
            self.highlightMoveIndex = index
            self.updateAll()
            self.createRightBtnMenu(index, evt.globalPos())
            self.highlightMoveIndex = self.getPointIndex(
                self.imgView.mapToScene(self.imgView.mapFromParent(self.mapFromParent(QCursor.pos())))
            )
            self.updateAll()

    def eventFilter(self, obj: QObject, evt: QEvent):
        if not self.img or obj is not self.imgView.viewport() or evt.type() not in self.targetEventType:
            return super().eventFilter(obj, evt)
        if self.mode == LabelMode.PointMode:
            self.handlePointMode(evt)
        elif self.mode == LabelMode.LineMode:
            self.handleLineMode(evt)
        elif self.mode == LabelMode.AngleMode:
            self.handleAngleMode(evt)
        elif self.mode == LabelMode.CircleMode:
            self.handleCircleMode(evt)
        elif self.mode == LabelMode.MidpointMode:
            self.handleMidpointMode(evt)
        elif self.mode == LabelMode.VerticalMode:
            self.handleVerticalMode(evt)
        elif self.mode == LabelMode.MovePointMode:
            self.handleDragMode(evt)
        elif self.mode == LabelMode.ClearPointMode:
            self.handleClearPointMode(evt)
        if evt.type() == QMouseEvent.MouseMove:
            self.handleHighlightMove(evt)
        elif evt.type() == QMouseEvent.MouseButtonPress and QMouseEvent(evt).button() == Qt.RightButton:
            self.handleRightBtnMenu(evt)
        return super().eventFilter(obj, evt)

    # 自动出点
    def aiPoint(self):
        pass
