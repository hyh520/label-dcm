import math
from App.Settings import settings
import os
from PyQt5.QtCore import QPointF, QRectF


def getIndexShift(A: QPointF):
    return QPointF(A.x() * (1 + settings.shifting), A.y() * (1 - settings.shifting))


def getMidpoint(A: QPointF, B: QPointF):
    return QPointF((A.x() + B.x()) / 2, (A.y() + B.y()) / 2)


def getDistance(A: QPointF, B: QPointF):
    return ((A.x() - B.x()) * (A.x() - B.x()) + (A.y() - B.y()) * (A.y() - B.y())) ** 0.5


def getDistanceShift(A: QPointF, B: QPointF, C: QPointF):
    if math.fabs(A.x() - B.x()) < settings.eps:
        return QPointF(C.x() * (1 + settings.shifting), C.y())
    if math.fabs(A.y() - B.y()) < settings.eps:
        return QPointF(C.x(), C.y() * (1 - settings.shifting))
    if (A.x() - B.x()) * (A.y() - B.y()) < 0:
        return QPointF(C.x() * (1 + settings.shifting), C.y() * (1 + settings.shifting))
    return QPointF(C.x() * (1 + settings.shifting), C.y() * (1 - settings.shifting))


def getRadius(A: QPointF, B: QPointF, C: QPointF):
    return min(getDistance(B, A), getDistance(B, C)) * settings.ratioToRadius


def getDiagPoints(A: QPointF, B: QPointF, C: QPointF):
    r = getRadius(A, B, C)
    return QPointF(B.x() - r, B.y() - r), QPointF(B.x() + r, B.y() + r)


# Get the point dis from A in the ray AB
def getDisPoint(A: QPointF, B: QPointF, dis: float):
    ratio = dis / getDistance(A, B)
    return QPointF(A.x() + (B.x() - A.x()) * ratio, A.y() + (B.y() - A.y()) * ratio)


def getArcMidpoint(A: QPointF, B: QPointF, C: QPointF):
    return getDisPoint(
        B, getMidpoint(getDisPoint(B, A, settings.base), getDisPoint(B, C, settings.base)), getRadius(A, B, C))


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
    return math.degrees(math.acos(getDot(A, B, C) / getDistance(B, A) / getDistance(B, C)))


def getBeginDegree(A: QPointF, B: QPointF, C: QPointF):
    D = C if getCross(A, B, C) > 0 else A
    deg = getDegree(D, B, QPointF(B.x() + settings.base, B.y()))
    return 360 - deg if D.y() > B.y() else deg


def getDegreeShift(A: QPointF, B: QPointF):
    if A.x() + settings.eps < B.x() and math.fabs(A.y() - B.y()) < settings.eps:
        return QPointF(B.x() * (1 + settings.shifting), B.y())
    if A.x() + settings.eps < B.x() and A.y() > B.y() + settings.eps:
        return QPointF(B.x() * (1 + settings.shifting), B.y() * (1 - settings.shifting))
    if A.y() > B.y() + settings.eps and math.fabs(A.x() - B.x()) < settings.eps:
        return QPointF(B.x(), B.y() * (1 - settings.shifting))
    if A.x() > B.x() + settings.eps and A.y() > B.y() + settings.eps:
        return QPointF(B.x() * (1 - settings.shiftingMore), B.y() * (1 - settings.shifting))
    if A.x() > B.x() + settings.eps and math.fabs(A.y() - B.y()) < settings.eps:
        return QPointF(B.x() * (1 - settings.shiftingMore), B.y())
    if A.x() > B.x() + settings.eps and A.y() + settings.eps < B.y():
        return QPointF(B.x() * (1 - 12 * settings.shifting), B.y() * (1 + 4 * settings.shifting))
    if A.y() + settings.eps < B.y() and math.fabs(A.x() - B.x()) < settings.eps:
        return QPointF(B.x(), B.y() * (1 + settings.shifting))
    return QPointF(B.x() * (1 + settings.shifting), B.y() * (1 + settings.shifting))


def getMinBoundingRect(A: QPointF, B: QPointF):
    r = getDistance(A, B)
    return QRectF(QPointF(A.x() - r, A.y() - r), QPointF(A.x() + r, A.y() + r))


def isImgAccess(imgDir: str):
    return os.access(imgDir, os.R_OK)


# Key_1
# Value_1
#
# ---
#
# Key_2
# Value_2
#
# ---
#
# ......
#
# ---
#
# Key_n
# Value_n
#
def getDcmImgAndMdInfo(imgDir: str):
    import numpy
    from PIL import Image
    from pydicom import dcmread
    dcm = dcmread(imgDir)
    low = numpy.min(dcm.pixel_array)
    upp = numpy.max(dcm.pixel_array)
    # 16 Bit -> 8 Bit
    mat = numpy.floor_divide(dcm.pixel_array, (upp - low + 1) / 256)
    img = Image.fromarray(mat.astype(numpy.uint8)).toqpixmap()
    info = {'ID': dcm.PatientID, 'Name': dcm.PatientName, 'Birth Date': dcm.PatientBirthDate, 'Sex': dcm.PatientSex}
    mdInfo = ''
    first = True
    for key, val in info.items():
        if first:
            first = False
        else:
            mdInfo += '---\n\n'
        mdInfo += key + '\n\n' + str(val) + '\n\n'
    return img, mdInfo


# Windows 10
# SystemDrive:\HomePath\Pictures\
def getHomeImgDir():
    homeImgDir = os.getcwd()
    sysDriver = os.getenv('SystemDrive')
    if sysDriver:
        homeImgDir = sysDriver
        homePath = os.getenv('HomePath')
        if homePath:
            homeImgDir += homePath + r'\Pictures\\'
    return homeImgDir


def getLineKey(indexA: int, indexB: int):
    return (indexA, indexB) if indexA < indexB else (indexB, indexA)


def getAngleKey(indexA: int, indexB: int, indexC: int):
    return (indexA, indexB, indexC) if indexA < indexC else (indexC, indexB, indexA)