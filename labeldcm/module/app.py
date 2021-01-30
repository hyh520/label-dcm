from labeldcm.ui.UiForm import Ui_Form
from labeldcm.module.config import config
from labeldcm.module import static
from labeldcm.module.mode import LabelMode
from PyQt5.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QResizeEvent
from PyQt5.QtWidgets import QAction, QFileDialog, QGraphicsScene, QInputDialog, QMessageBox, QMenu, QWidget
from typing import Dict, Optional, Tuple, Set

class LabelApp(QWidget, Ui_Form):
    def initColorList(self):
        size = self.colorList.iconSize()
        index = 0
        defaultIndex = -1
        for color in config.colorList:
            if color == config.defaultColor:
                defaultIndex = index
            colorIcon = QPixmap(size)
            colorIcon.fill(QColor(color))
            self.colorList.addItem(QIcon(colorIcon), color.capitalize())
            index += 1
        self.colorList.setCurrentIndex(defaultIndex)

    # TODO: Init UI style
    def initUIStyle(self):
        pass
        # Example
        # self.setWindowTitle('LabelDcm')
        # self.setStyleSheet('QWidget { color: gray }')

    def initEventConnections(self):
        self.imgView.viewport().installEventFilter(self)
        self.uploadBtn.clicked.connect(self.uploadImg)
        self.saveBtn.clicked.connect(self.saveImg)
        self.initBtn.clicked.connect(self.initImgWithPoints)
        self.pointBtn.clicked.connect(lambda: self.toMode(LabelMode.PointMode))
        self.lineBtn.clicked.connect(lambda: self.toMode(LabelMode.LineMode))
        self.angleBtn.clicked.connect(lambda: self.toMode(LabelMode.AngleMode))
        self.circleBtn.clicked.connect(lambda: self.toMode(LabelMode.CircleMode))
        self.midpointBtn.clicked.connect(lambda: self.toMode(LabelMode.MidpointMode))
        self.verticalBtn.clicked.connect(lambda: self.toMode(LabelMode.VerticalMode))
        self.colorList.currentIndexChanged.connect(self.changeColor)
        self.clearBtn.clicked.connect(self.clearLabels)

    def __init__(self):
        # Init UI
        super(LabelApp, self).__init__()
        self.setupUi(self)
        self.retranslateUi(self)
        self.initColorList()
        self.initUIStyle()

        # Init Right Button Menu
        self.rightBtnMenu = QMenu(self)

        # Init Event
        self.targetEventType = [QMouseEvent.MouseButtonPress, QMouseEvent.MouseMove, QMouseEvent.MouseButtonRelease]
        self.initEventConnections()

        # Init Label Mode
        self.mode = LabelMode.DefaultMode

        # Init Color
        self.color = QColor(config.defaultColor)

        # Init Image
        self.src: Optional[QPixmap] = None
        self.img: Optional[QPixmap] = None
        self.ratioFromOld = 1
        self.ratioToSrc = 1

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

        # Init Highlight
        self.highlightMoveIndex = -1
        self.highlightPoints: Set[int] = set()

        if config.debug:
            self.test()

    def initImg(self):
        self.src = None
        self.img = None
        self.ratioFromOld = 1
        self.ratioToSrc = 1
        self.patientInfo.setMarkdown('')

    def initIndex(self):
        self.indexA = -1
        self.indexB = -1
        self.indexC = -1

    def initHighlight(self):
        self.highlightMoveIndex = -1
        self.highlightPoints.clear()

    def initExceptImg(self):
        self.initIndex()
        self.points.clear()
        self.lines.clear()
        self.angles.clear()
        self.circles.clear()
        self.pivots.clear()
        self.initHighlight()

    # Except UI, Event, Label Mode, Color
    def initAll(self):
        self.initImg()
        self.initExceptImg()

    # Update based on source
    def updateImg(self):
        if not self.src:
            self.initImg()
            return None
        old = self.img if self.img else self.src
        size = QSize(
            self.imgView.width() - 2 * self.imgView.lineWidth(), self.imgView.height() - 2 * self.imgView.lineWidth()
        )
        self.img = self.src.scaled(size, Qt.KeepAspectRatio)
        self.ratioFromOld = self.img.width() / old.width()
        self.ratioToSrc = self.src.width() / self.img.width()

    # Update based on resize event
    def updatePoints(self):
        if not self.img or not self.points or self.ratioFromOld == 1:
            return None
        for point, _ in self.points.values():
            point.setX(point.x() * self.ratioFromOld)
            point.setY(point.y() * self.ratioFromOld)
        self.ratioFromOld = 1

    def getSrcPoint(self, point: QPointF):
        return QPointF(point.x() * self.ratioToSrc, point.y() * self.ratioToSrc)

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

    def updateLabels(self, img: Optional[QPixmap], toSrc: bool):
        self.labelPoints(img, toSrc)
        self.labelLines(img, toSrc)
        self.labelAngles(img, toSrc)
        self.labelCircles(img, toSrc)

    # Update based on latest image
    def updateImgView(self):
        scene = QGraphicsScene()
        if self.img:
            scene.addPixmap(self.img)
        self.imgView.setScene(scene)

    def updatePivotsInfo(self):
        if not self.img or not self.points or not self.pivots:
            self.pivotsInfo.setMarkdown('')
            return None
        pivots = list(self.pivots)
        pivots.sort()
        mdInfo = ''
        for index in pivots:
            point = self.getSrcPoint(self.points[index][0])
            mdInfo += str(index) + ': (' + str(round(point.x(), 2)) + ', ' + str(round(point.y(), 2)) + ')\n\n'
        self.pivotsInfo.setMarkdown(mdInfo)

    def updateAll(self):
        # The order is immutable
        # img -> points
        # points -> labels, pivotsInfo
        # labels -> imgView
        self.updateImg()
        self.updatePoints()
        self.updateLabels(self.img, False)
        self.updateImgView()
        self.updatePivotsInfo()

    def resizeEvent(self, _: QResizeEvent):
        self.updateAll()

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

    def warning(self, text: str):
        QMessageBox.warning(self, 'Warning', text)

    # DICOM (*.dcm)
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

    def getImgPoint(self, point: QPointF):
        return QPointF(point.x() / self.ratioToSrc, point.y() / self.ratioToSrc)

    def addRealPoint(self, index: int, x: float, y: float):
        if self.img and index > -1:
            self.points[index] = self.getImgPoint(QPointF(x, y)), self.color

    def getNewIndex(self):
        return max(self.points.keys() if self.points else [0]) + 1

    def addNewRealPoint(self, x: float, y: float):
        self.addRealPoint(self.getNewIndex(), x, y)

    # TODO: Init image with points
    def initImgWithPoints(self):
        if not self.img:
            return None
        self.initExceptImg()
        # Example
        # self.addRealPoint(1, 300, 200)
        # self.addNewRealPoint(300, 300)
        self.updateAll()

    def toMode(self, mode: LabelMode):
        self.eraseHighlight()
        # Switch to mode or cancel current mode
        self.mode = mode if self.mode != mode else LabelMode.DefaultMode

    def changeColor(self):
        self.color = QColor(config.colorList[self.colorList.currentIndex()])

    def clearLabels(self):
        self.initExceptImg()
        self.updateAll()

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

    def getIndexCnt(self):
        return len([i for i in [self.indexA, self.indexB, self.indexC] if i != -1])

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

    def handleDragMode(self, evt: QMouseEvent):
        point = self.imgView.mapToScene(evt.pos())
        if evt.type() == QMouseEvent.MouseButtonPress and self.getIndexCnt() == 0:
            self.triggerIndex(self.getPointIndex(point))
        elif evt.type() == QMouseEvent.MouseMove and self.getIndexCnt() == 1 and not self.isPointOutOfBound(point):
            self.points[self.indexA][0].setX(point.x())
            self.points[self.indexA][0].setY(point.y())
        elif evt.type() == QMouseEvent.MouseButtonRelease and self.getIndexCnt() == 1:
            self.triggerIndex(self.indexA)

    def handlePointMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        point = self.imgView.mapToScene(evt.pos())
        index = self.getPointIndex(point)
        if index != -1:
            self.points[index] = self.points[index][0], self.color
        else:
            self.addPoint(point)

    def handleLineMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        self.triggerIndex(self.getPointIndex(self.imgView.mapToScene(evt.pos())))
        if self.getIndexCnt() == 2:
            self.addLine(self.indexA, self.indexB)
            self.endTriggerWith(self.indexB)

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

    def handleCircleMode(self, evt: QMouseEvent):
        point = self.imgView.mapToScene(evt.pos())
        if evt.type() == QMouseEvent.MouseButtonPress:
            if self.getIndexCnt() == 0:
                self.triggerIndex(self.addPoint(point))
                self.triggerIndex(self.addPoint(QPointF(point.x() + 2 * config.eps, point.y() + 2 * config.eps)))
                self.addCircle(self.indexA, self.indexB)
            elif self.getIndexCnt() == 2:
                self.endTriggerWith(self.indexB)
        elif evt.type() == QMouseEvent.MouseMove and self.getIndexCnt() == 2 and not self.isPointOutOfBound(point):
            self.points[self.indexB][0].setX(point.x())
            self.points[self.indexB][0].setY(point.y())

    def handleMidpointMode(self, evt: QMouseEvent):
        if evt.type() != QMouseEvent.MouseButtonPress:
            return None
        self.triggerIndex(self.getPointIndex(self.imgView.mapToScene(evt.pos())))
        if self.getIndexCnt() == 2:
            if static.getLineKey(self.indexA, self.indexB) in self.lines:
                A = self.points[self.indexA][0]
                B = self.points[self.indexB][0]
                self.addPoint(static.getMidpoint(A, B))
                self.endTriggerWith(self.indexB)
            else:
                self.triggerIndex(self.indexA)

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
                    self.addLine((self.indexA if static.getDistance(A, D) < static.getDistance(B, D) else self.indexB),
                                 indexD)
                self.addLine(self.indexC, indexD)
                self.endTriggerWith(self.indexC)

    def handleHighlightMove(self, evt: QMouseEvent):
        self.highlightMoveIndex = self.getPointIndex(self.imgView.mapToScene(evt.pos()))
        self.updateAll()

    def modifyIndex(self, index: int):
        newIndex, modify = QInputDialog.getInt(self,
            'Modify Index', 'Please input a natural number.', index, 0, step=1)
        if not modify or newIndex == index:
            return None
        if newIndex in self.points:
            self.warning('The index already exists!')
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
        modifyIndex = QAction('Modify Index', self.rightBtnMenu)
        modifyIndex.triggered.connect(lambda: self.modifyIndex(index))
        switchPivotState = QAction('Remove from pivots' if index in self.pivots else 'Add to pivots', self.rightBtnMenu)
        switchPivotState.triggered.connect(lambda: self.switchPivotState(index))
        erasePoint = QAction('Erase point', self.rightBtnMenu)
        erasePoint.triggered.connect(lambda: self.erasePoint(index))
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
                self.imgView.mapToScene(self.imgView.mapFromParent(self.mapFromParent(QCursor.pos()))))
            self.updateAll()

    def eventFilter(self, obj: QObject, evt: QEvent):
        if not self.img or obj is not self.imgView.viewport() or evt.type() not in self.targetEventType:
            return super().eventFilter(obj, evt)
        if self.mode == LabelMode.DragMode:
            self.handleDragMode(evt)
        elif self.mode == LabelMode.PointMode:
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
        if evt.type() == QMouseEvent.MouseMove:
            self.handleHighlightMove(evt)
        elif evt.type() == QMouseEvent.MouseButtonPress and QMouseEvent(evt).button() == Qt.RightButton:
            self.handleRightBtnMenu(evt)
        return super().eventFilter(obj, evt)

    # Debug Test
    def test(self):
        pass
        # self.loadImg('path to an image file')
        # self.addRealPoint(1, 300, 200)
        # self.addRealPoint(2, 200, 200)
        # self.addRealPoint(3, 300, 300)
        # self.addLine(1, 2)
        # self.addLine(1, 3)
        # self.addAngle(2, 1, 3)
        # self.addCircle(1, 2)
        # self.addPivots(1)
        # self.addPivots(2)
        # self.updateAll()
