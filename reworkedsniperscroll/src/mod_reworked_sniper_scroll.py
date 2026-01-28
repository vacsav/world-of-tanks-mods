import logging
from AvatarInputHandler.DynamicCameras.SniperCamera import SniperCamera
_logger = logging.getLogger(__name__)


def overrideIn(cls, condition=lambda: True):

    def _overrideMethod(func):
        if not condition():
            return func

        funcName = func.__name__

        if funcName.startswith("__") and funcName != "__init__":
            funcName = "_" + cls.__name__ + funcName

        old = getattr(cls, funcName)

        def wrapper(*args, **kwargs):
            return func(old, *args, **kwargs)

        setattr(cls, funcName, wrapper)
        return wrapper
    return _overrideMethod


orig_init = SniperCamera.__init__
def mod_init(self, *args, **kwargs):
    orig_init(self, *args, **kwargs)
    self.__zoomStorage = 0.0
SniperCamera.__init__ = mod_init


@overrideIn(SniperCamera)
def disable(func, self):
    func(self)
    self.__zoomStorage = 0.0


@overrideIn(SniperCamera)
def __setupZoom(func, self, dz):
    if dz == 0:
        return
    else:
        zooms = self._SniperCamera__getZooms()
        prevZoom = self._SniperCamera__zoom
        if abs(dz) > 1:
            dz = dz / float(abs(dz))
        scrollSense = self._userCfg['scrollSensitivity']
        if scrollSense < 1 or scrollSense > 10:
            scrollSense = 1
        minZoom = self._SniperCamera__zoom == zooms[0]
        realMax = max([z for z in zooms if z > 0])
        maxZoom = self._SniperCamera__zoom == realMax
        if minZoom and dz < 0 and self._SniperCamera__onChangeControlMode is not None:
            self._SniperCamera__onChangeControlMode(True)
        if dz < 0 and minZoom or dz > 0 and maxZoom:
            dzStep = 0
        else:
            dzStep = dz
        self.__zoomStorage += dzStep
        stepCount = int(self.__zoomStorage / scrollSense)
        if stepCount != 0:
            self.__zoomStorage -= stepCount * scrollSense
        else:
            return
        if stepCount > 0:
            for elem in zooms:
                if self._SniperCamera__zoom < elem:
                    self._SniperCamera__zoom = elem
                    self._cfg['zoom'] = self._SniperCamera__zoom
                    stepCount -= 1
                    if stepCount <= 0:
                        break
        elif stepCount < 0:
            for i in range(len(zooms) - 1, -1, -1):
                if self._SniperCamera__zoom > zooms[i]:
                    self._SniperCamera__zoom = zooms[i]
                    self._cfg['zoom'] = self._SniperCamera__zoom
                    stepCount += 1
                    if stepCount >= 0:
                        break
        if prevZoom != self._SniperCamera__zoom:
            self._SniperCamera__applyZoom(self._SniperCamera__zoom)
        return