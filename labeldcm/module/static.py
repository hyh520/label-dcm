from labeldcm.module.config import config
import math
import numpy
import os
from PIL import Image
from pydicom import dcmread
from PyQt5.QtCore import QPointF, QRectF

# 判断文件是否可读
def isImgAccess(imgDir: str):
    return os.access(imgDir, os.R_OK)

def toDate(date: str):
    return date[0:4] + '年' + date[4:6] + '月' + date[6:8] + '日'

def toAge(age: str):
    str1: str = ''
    if age[0] != '0':
        str1 = age[0:3]
    elif age[1] != '0':
        str1 = age[1:3]
    elif age[2] != '0':
        str1 = age[2]
    if age[3] == 'Y':
        return str1 + '岁'
    elif age[3] == 'M':
        return str1 + '月'
    elif age[3] == 'W':
        return str1 + '周'
    elif age[3] == 'D':
        return str1 + '天'
    return str1

# 得到dcm文件的qpixmap和包含的信息
def getDcmImgAndMdInfo(imgDir: str):
    dcm = dcmread(imgDir)
    low = numpy.min(dcm.pixel_array)
    upp = numpy.max(dcm.pixel_array)
    # 16 Bit -> 8 Bit
    mat = numpy.floor_divide(dcm.pixel_array, (upp - low + 1) / 256)
    img = Image.fromarray(mat.astype(numpy.uint8)).toqpixmap()
    info = {
        '患者ID': dcm.PatientID, '姓名': dcm.PatientName, '出生日期': toDate(dcm.PatientBirthDate),
        '性别': dcm.PatientSex, '体重': dcm.PatientWeight, '检查开始日期': toDate(dcm.StudyDate),
        '检查日期': toDate(dcm.SeriesDate), '检查时患者年龄': toAge(dcm.PatientAge), '检查部位': dcm.BodyPartExamined
    }
    mdInfo = ''
    first = True
    for key, val in info.items():
        if first:
            first = False
        else:
            mdInfo += '---\n\n'
        mdInfo += key + ': ' + str(val) + '\n\n'
    return img, mdInfo

# Windows 10
# SystemDrive:\HomePath\Pictures\
def getHomeImgDir():
    homeImgDir = os.getcwd()
    if sysDriver := os.getenv('SystemDrive'):
        homeImgDir = sysDriver
        if homePath := os.getenv('HomePath'):
            homeImgDir = os.path.join(homeImgDir, homePath, 'Pictures')
    return homeImgDir

# 文本显示位置在右上角
def getIndexShift(A: QPointF):
    return QPointF(A.x() + config.indexShifting, A.y() - config.indexShifting)

# 求中点
def getMidpoint(A: QPointF, B: QPointF):
    return QPointF((A.x() + B.x()) / 2, (A.y() + B.y()) / 2)

# 求距离
def getDistance(A: QPointF, B: QPointF):
    distance = ((A.x() - B.x()) * (A.x() - B.x()) + (A.y() - B.y()) * (A.y() - B.y())) ** 0.5
    return distance if distance > config.eps else config.eps

# 线段距离显示位置
def getDistanceShift(A: QPointF, B: QPointF, C: QPointF):
    if math.fabs(A.x() - B.x()) < config.eps:
        return QPointF(C.x() + config.distanceShifting, C.y())
    if math.fabs(A.y() - B.y()) < config.eps:
        return QPointF(C.x(), C.y() - config.distanceShifting)
    if (A.x() - B.x()) * (A.y() - B.y()) < 0:
        return QPointF(C.x() + config.distanceShifting, C.y() + config.distanceShifting)
    return QPointF(C.x() + config.distanceShifting, C.y() - config.distanceShifting)

def getRadius(A: QPointF, B: QPointF, C: QPointF):
    return min(getDistance(B, A), getDistance(B, C)) * config.ratioToRadius

def getDiagPoints(A: QPointF, B: QPointF, C: QPointF):
    r = getRadius(A, B, C)
    return QPointF(B.x() - r, B.y() - r), QPointF(B.x() + r, B.y() + r)

def getDisPoint(A: QPointF, B: QPointF, dis: float):
    ratio = dis / getDistance(A, B)
    return QPointF(A.x() + (B.x() - A.x()) * ratio, A.y() + (B.y() - A.y()) * ratio)

def getArcMidpoint(A: QPointF, B: QPointF, C: QPointF):
    return getDisPoint(
        B, getMidpoint(getDisPoint(B, A, config.base), getDisPoint(B, C, config.base)), getRadius(A, B, C)
    )

# BA · BC
def getDot(A: QPointF, B: QPointF, C: QPointF):
    BA = (A.x() - B.x(), A.y() - B.y())
    BC = (C.x() - B.x(), C.y() - B.y())
    return BA[0] * BC[0] + BA[1] * BC[1]

# BA × BC
def getCross(A: QPointF, B: QPointF, C: QPointF):
    BA = (A.x() - B.x(), A.y() - B.y())
    BC = (C.x() - B.x(), C.y() - B.y())
    return BA[0] * BC[1] - BC[0] * BA[1]

def getDegree(A: QPointF, B: QPointF, C: QPointF):
    return math.degrees(math.acos(min(1, max(-1, getDot(A, B, C) / getDistance(B, A) / getDistance(B, C)))))

def getBeginDegree(A: QPointF, B: QPointF, C: QPointF):
    D = C if getCross(A, B, C) > 0 else A
    deg = getDegree(D, B, QPointF(B.x() + config.base, B.y()))
    return 360 - deg if D.y() > B.y() else deg

def getDegreeShift(A: QPointF, B: QPointF):
    # Up
    if A.y() > B.y() + config.eps and math.fabs(A.x() - B.x()) < config.eps:
        return QPointF(B.x(), B.y() - config.degreeShiftingBase)
    # Down
    if A.y() + config.eps < B.y() and math.fabs(A.x() - B.x()) < config.eps:
        return QPointF(B.x(), B.y() + config.degreeShiftingBase)
    # Left
    if A.x() > B.x() + config.eps and math.fabs(A.y() - B.y()) < config.eps:
        return QPointF(B.x() - config.degreeShiftingMore, B.y())
    # Right
    if A.x() + config.eps < B.x() and math.fabs(A.y() - B.y()) < config.eps:
        return QPointF(B.x() + config.degreeShiftingBase, B.y())
    # Top Right
    if A.x() + config.eps < B.x() and A.y() > B.y() + config.eps:
        return QPointF(B.x() + config.degreeShiftingBase, B.y() - config.degreeShiftingBase)
    # Top Left
    if A.x() > B.x() + config.eps and A.y() > B.y() + config.eps:
        return QPointF(B.x() - config.degreeShiftingMore, B.y() - config.degreeShiftingBase)
    # Bottom Left
    if A.x() > B.x() + config.eps and A.y() + config.eps < B.y():
        return QPointF(B.x() - config.degreeShiftingMore, B.y() + config.degreeShiftingBase)
    # Bottom Right
    return QPointF(B.x() + config.degreeShiftingBase, B.y() + config.degreeShiftingBase)

def getMinBoundingRect(A: QPointF, B: QPointF):
    r = getDistance(A, B)
    return QRectF(QPointF(A.x() - r, A.y() - r), QPointF(A.x() + r, A.y() + r))

# 返回排序的线标号
def getLineKey(indexA: int, indexB: int):
    return (indexA, indexB) if indexA < indexB else (indexB, indexA)

def getAngleKey(indexA: int, indexB: int, indexC: int):
    return (indexA, indexB, indexC) if indexA < indexC else (indexC, indexB, indexA)

def isOnALine(A: QPointF, B: QPointF, C: QPointF):
    return math.fabs((A.x() - C.x()) * (A.y() - B.y()) - (A.x() - B.x()) * (A.y() - C.y())) < config.eps

# AB: ax + by + c = 0
def getFootPoint(A: QPointF, B: QPointF, C: QPointF):
    a = A.y() - B.y()
    b = B.x() - A.x()
    c = -a * A.x() - b * A.y()
    return QPointF(
        (b * b * C.x() - a * b * C.y() - a * c) / (a * a + b * b),
        (a * a * C.y() - a * b * C.x() - b * c) / (a * a + b * b)
    )

def isOnSegment(A: QPointF, B: QPointF, C: QPointF):
    return min(A.x(), B.x()) < C.x() + config.eps and C.x() < max(A.x(), B.x()) + config.eps
