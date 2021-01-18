from App import Static
from App.LabelMode import LabelMode
from App.Settings import settings
from App.UiForm import Ui_Form
from PyQt5.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QMouseEvent, QPainter, QPen, QPixmap, QResizeEvent
from PyQt5.QtWidgets import QAction, QFileDialog, QGraphicsScene, QInputDialog, QMessageBox, QMenu, QWidget
from typing import Dict, Optional, Tuple, Set


class LabelApp(QWidget, Ui_Form):
    def initColorList(self):
        size = self.colorList.iconSize()
        index = 0
        defaultIndex = -1
        for color in settings.colorList:
            if color == settings.defaultColor:
                defaultIndex = index
            colorIcon = QPixmap(size)
            colorIcon.fill(QColor(color))
            self.colorList.addItem(QIcon(colorIcon), color.capitalize())
            index += 1
        self.colorList.setCurrentIndex(defaultIndex)

    # TODO: Init UI style
    def initUIStyle(self):
        # Example
        # self.setWindowTitle('LabelDcm')
        # self.setStyleSheet('QWidget { color: gray }')
        pass

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
        self.color = QColor(settings.defaultColor)

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
        self.highlightLine: Optional[Tuple[int, int]] = None
        self.highlightCircle: Optional[Tuple[int, int]] = None

        if settings.debug:
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
        self.highlightLine = None
        self.highlightCircle = None

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
        size = QSize(self.imgView.width() - 2 * self.imgView.lineWidth(),
                     self.imgView.height() - 2 * self.imgView.lineWidth())
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
            pen.setWidthF(settings.pointWidth * self.ratioToSrc)
            font.setPointSizeF(settings.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(settings.pointWidth)
            font.setPointSizeF(settings.fontSize)
        painter.setFont(font)
        for index, (point, color) in self.points.items():
            labelPoint: QPointF
            if toSrc:
                pen.setColor(color)
                labelPoint = self.getSrcPoint(point)
            else:
                pen.setColor(color if index != self.highlightMoveIndex and index not in self.highlightPoints
                             else QColor.lighter(color))
                labelPoint = point
            painter.setPen(pen)
            painter.drawPoint(labelPoint)
            painter.drawText(Static.getIndexShift(labelPoint), str(index))
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
            pen.setWidthF(settings.lineWidth * self.ratioToSrc)
            font.setPointSizeF(settings.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(settings.lineWidth)
            font.setPointSizeF(settings.fontSize)
        painter.setFont(font)
        for (indexA, indexB), color in self.lines.items():
            pen.setColor(color if (indexA, indexB) != self.highlightLine else QColor.lighter(color))
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            srcA = self.getSrcPoint(A)
            srcB = self.getSrcPoint(B)
            labelPoint: QPointF
            if toSrc:
                painter.drawLine(srcA, srcB)
                labelPoint = Static.getMidpoint(srcA, srcB)
            else:
                painter.drawLine(A, B)
                labelPoint = Static.getMidpoint(A, B)
            painter.drawText(Static.getDistanceShift(A, B, labelPoint), str(round(Static.getDistance(srcA, srcB), 2)))
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
            pen.setWidthF(settings.angleWidth * self.ratioToSrc)
            font.setPointSizeF(settings.fontSize * self.ratioToSrc)
        else:
            pen.setWidthF(settings.angleWidth)
            font.setPointSizeF(settings.fontSize)
        painter.setFont(font)
        for (indexA, indexB, indexC), color in self.angles.items():
            pen.setColor(color)
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            C = self.points[indexC][0]
            D, E = Static.getDiagPoints(self.points[indexA][0], B, C)
            F = Static.getArcMidpoint(A, B, C)
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
            deg = Static.getDegree(A, B, C)
            painter.drawArc(labelRect, int(Static.getBeginDegree(A, B, C) * 16), int(deg * 16))
            painter.drawText(Static.getDegreeShift(labelPointA, labelPointB), str(round(deg, 2)) + '°')
        painter.end()

    def labelCircles(self, img: Optional[QPixmap], toSrc: bool):
        if not img or not self.circles:
            return None
        painter = QPainter()
        painter.begin(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen()
        pen.setCapStyle(Qt.RoundCap)
        pen.setWidthF(settings.lineWidth if not toSrc else settings.lineWidth * self.ratioToSrc)
        for (indexA, indexB), color in self.circles.items():
            pen.setColor(color if (indexA, indexB) != self.highlightCircle else QColor.lighter(color))
            painter.setPen(pen)
            A = self.points[indexA][0]
            B = self.points[indexB][0]
            painter.drawEllipse(Static.getMinBoundingRect(A, B) if not toSrc
                                else Static.getMinBoundingRect(self.getSrcPoint(A), self.getSrcPoint(B)))
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
        if self.mode == LabelMode.CircleMode or self.mode == LabelMode.VerticalMode:
            self.erasePoint(self.indexA)
            self.erasePoint(self.indexB)
            self.erasePoint(self.indexC)
        self.initIndex()
        self.initHighlight()
        self.updateAll()

    def warning(self, text: str):
        QMessageBox.warning(self, 'Warning', text)

    # DICOM (*.dcm)
    def loadDcmImg(self, imgDir: str):
        if Static.isImgAccess(imgDir):
            self.src, mdInfo = Static.getDcmImgAndMdInfo(imgDir)
            self.patientInfo.setMarkdown(mdInfo)
            self.updateAll()
        else:
            self.warning('The image file is not found or unreadable!')

    # JPEG (*.jpg;*.jpeg;*.jpe), PNG (*.png)
    def loadImg(self, imgDir: str):
        if Static.isImgAccess(imgDir):
            self.src = QPixmap()
            self.src.load(imgDir)
            self.updateAll()
        else:
            self.warning('The image file is not found or unreadable!')

    def uploadImg(self):
        caption = 'Open Image File'
        extFilter = 'DICOM (*.dcm);;JPEG (*.jpg;*.jpeg;*.jpe);;PNG (*.png)'
        dcmFilter = 'DICOM (*.dcm)'
        imgDir, imgExt = QFileDialog.getOpenFileName(self, caption, Static.getHomeImgDir(), extFilter, dcmFilter)
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
        imgDir, _ = QFileDialog.getSaveFileName(self, caption, Static.getHomeImgDir(), extFilter, initFilter)
        if imgDir:
            img.save(imgDir)

    def getImgPoint(self, point: QPointF):
        return QPointF(point.x() / self.ratioToSrc, point.y() / self.ratioToSrc)

    def addRealPoint(self, index: int, x: float, y: float):
        if self.img and index > -1:
            self.points[index] = self.getImgPoint(QPointF(x, y)), self.color

    # TODO: Init image with points
    def initImgWithPoints(self):
        if not self.img:
            return None
        self.initExceptImg()
        # Example
        # self.addRealPoint(1, 300, 200)
        self.updateAll()

    def toMode(self, mode: LabelMode):
        self.eraseHighlight()
        # Switch to mode or cancel current mode
        self.mode = mode if self.mode != mode else LabelMode.DefaultMode

    def changeColor(self):
        self.color = QColor(settings.colorList[self.colorList.currentIndex()])

    def clearLabels(self):
        self.initExceptImg()
        self.updateAll()

    def getPointIndex(self, point: QPointF):
        if not self.img or not self.points:
            return -1
        distance = settings.pointWidth - settings.eps
        # Index -1 means the point does not exist
        index = -1
        for idx, (pt, _) in self.points.items():
            dis = Static.getDistance(point, pt)
            if dis < distance:
                distance = dis
                index = idx
        return index

    def addIndex(self, index: int):
        if not self.img or not self.points or index == -1:
            return None
        if index in [self.indexA, self.indexB, self.indexC]:
            indexs = [_ for _ in [self.indexA, self.indexB, self.indexC] if _ != index]
            self.indexA = indexs[0]
            self.indexB = indexs[1]
            self.indexC = -1
            self.highlightPoints.remove(index)
        else:
            indexs = [_ for _ in [self.indexA, self.indexB, self.indexC] if _ != -1]
            indexs.append(index)
            while len(indexs) < 3:
                indexs.append(-1)
            self.indexA = indexs[0]
            self.indexB = indexs[1]
            self.indexC = indexs[2]
            self.highlightPoints.add(index)

    def getIndexCnt(self):
        return len([_ for _ in [self.indexA, self.indexB, self.indexC] if _ != -1])

    def addPoint(self, index: int, x: float, y: float):
        if self.img and index > -1:
            self.points[index] = QPointF(x, y), self.color

    def addLine(self, indexA: int, indexB: int):
        if self.img and indexA in self.points and indexB in self.points:
            self.lines[Static.getLineKey(indexA, indexB)] = self.color

    def addAngle(self, indexA: int, indexB: int, indexC: int):
        if self.img and Static.getLineKey(indexA, indexB) in self.lines \
                and Static.getLineKey(indexB, indexC) in self.lines:
            self.angles[Static.getAngleKey(indexA, indexB, indexC)] = self.color

    def addCircle(self, indexA: int, indexB: int):
        if self.img and indexA in self.points and indexB in self.points:
            self.circles[(indexA, indexB)] = self.color

    # TODO: Handle events about imgView

    def handleDragMode(self, evt: QMouseEvent):
        pass

    def handlePointMode(self, evt: QMouseEvent):
        pass

    def handleLineMode(self, evt: QMouseEvent):
        pass

    def handleAngleMode(self, evt: QMouseEvent):
        pass

    def handleCircleMode(self, evt: QMouseEvent):
        pass

    def handleMidpointMode(self, evt: QMouseEvent):
        pass

    def handleVerticalMode(self, evt: QMouseEvent):
        pass

    def handleHighlightMove(self, evt: QMouseEvent):
        self.highlightMoveIndex = self.getPointIndex(self.imgView.mapToScene(evt.pos()))
        self.updateAll()

    def modifyIndex(self, index: int):
        newIndex, modify = QInputDialog.getInt(self, 'Modify Index', 'Please input a natural number.', index, 0, step=1)
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
                self.lines[Static.getLineKey(newIndex, fixedIndex)] = self.lines[line]
                del self.lines[line]
        for angle in list(self.angles.keys()):
            if index in angle:
                if index == angle[1]:
                    self.angles[angle[0], newIndex, angle[2]] = self.angles[angle]
                else:
                    fixedIndex = angle[0] + angle[2] - index
                    self.angles[Static.getAngleKey(newIndex, angle[1], fixedIndex)] = self.angles[angle]
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
        self.loadImg(r'C:\Users\Makise Von\Pictures\test.jpg')
        self.addRealPoint(1, 300, 200)
        self.addRealPoint(2, 200, 200)
        self.addRealPoint(3, 300, 300)
        self.addLine(1, 2)
        self.addLine(1, 3)
        self.addAngle(2, 1, 3)
        self.addCircle(1, 2)
        self.addPivots(1)
        self.addPivots(2)
        self.updateAll()
        pass
