import Math, BigWorld, BattleReplay, constants, logging
from Math import Matrix
from realm import CURRENT_REALM
from AvatarInputHandler.DynamicCameras.ArcadeCamera import ArcadeCamera
from AvatarInputHandler.DynamicCameras.SniperCamera import SniperCamera
from gui.Scaleform.daapi.view.battle.shared.crosshair.container import CrosshairPanelContainer
from gui.Scaleform.locale.INGAME_GUI import INGAME_GUI
from gui.battle_control import event_dispatcher
from helpers import i18n
_logger = logging.getLogger(__name__)


def isClientLesta():
    return CURRENT_REALM == 'RU'


def isClientWG():
    return not isClientLesta()


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


@overrideIn(ArcadeCamera, condition=isClientLesta)
def enable(func, self, preferredPos = None, closesDist = False, postmortemParams = None, turretYaw = None, gunPitch = None, camTransitionParams = None, initialVehicleMatrix = None, arcadeState = None):
    replayCtrl = BattleReplay.g_replayCtrl
    if replayCtrl.isRecording:
        replayCtrl.setAimClipPosition(self._ArcadeCamera__aimOffset)
    self.measureDeltaTime()
    player = BigWorld.player()
    vehicle = player.getVehicleAttached()
    if player.observerSeesAll() and player.arena.period == constants.ARENA_PERIOD.BATTLE and vehicle and vehicle.id == player.playerVehicleID:
        self.delayCallback(0.0, self.enable, preferredPos, closesDist, postmortemParams, turretYaw, gunPitch, camTransitionParams, initialVehicleMatrix)
        return
    elif initialVehicleMatrix is None:
        initialVehicleMatrix = player.getOwnVehicleMatrix(Math.Matrix(self.vehicleMProv)) if vehicle is None else vehicle.matrix
    vehicleMProv = initialVehicleMatrix
    if not self._ArcadeCamera__isInArcadeZoomState() or arcadeState is not None:
        if arcadeState is None:
            state = None
            newCameraDistance = self._cfg['distRange'].max
        else:
            self._ArcadeCamera__zoomStateSwitcher.switchToState(arcadeState.zoomSwitcherState)
            state = self._ArcadeCamera__zoomStateSwitcher.getCurrentState()
            newCameraDistance = arcadeState.camDist
        self._ArcadeCamera__updateProperties(state = state)
        self._ArcadeCamera__updateCameraSettings(newCameraDistance)
        self._ArcadeCamera__inputInertia.glideFov(self._ArcadeCamera__calcRelativeDist())
        if arcadeState is None:
            self._ArcadeCamera__aimingSystem.aimMatrix = self._ArcadeCamera__calcAimMatrix()
    camDist = None
    if self._ArcadeCamera__postmortemMode:
        if postmortemParams is not None:
            self._ArcadeCamera__aimingSystem.yaw = postmortemParams[0][0]
            self._ArcadeCamera__aimingSystem.pitch = postmortemParams[0][1]
            camDist = postmortemParams[1]
        else:
            camDist = self._ArcadeCamera__distRange.max
    elif closesDist:
        camDist = self._ArcadeCamera__distRange.min
    replayCtrl = BattleReplay.g_replayCtrl
    if replayCtrl.isPlaying and not replayCtrl.isServerSideReplay:
        camDist = None
        vehicle = BigWorld.entity(replayCtrl.playerVehicleID)
        if vehicle is not None:
            vehicleMProv = vehicle.matrix
    if camDist is not None:
        self.setCameraDistance(camDist)
    else:
        self._ArcadeCamera__inputInertia.teleport(self._ArcadeCamera__calcRelativeDist())
    self.vehicleMProv = vehicleMProv
    self._ArcadeCamera__setDynamicCollisions(True)
    self._ArcadeCamera__aimingSystem.enable(preferredPos, turretYaw, gunPitch)
    self._ArcadeCamera__aimingSystem.aimMatrix = self._ArcadeCamera__calcAimMatrix()
    if camTransitionParams is not None and BigWorld.camera() is not self._ArcadeCamera__cam:
        cameraTransitionDuration = camTransitionParams.get('cameraTransitionDuration', -1)
        if cameraTransitionDuration > 0:
            self._ArcadeCamera__setupCameraTransition(cameraTransitionDuration)
        else:
            self._ArcadeCamera__setCamera()
    else:
        self._ArcadeCamera__setCamera()
    self._ArcadeCamera__cameraUpdate()
    self.delayCallback(0.0, self._ArcadeCamera__cameraUpdate)
    from gui import g_guiResetters
    g_guiResetters.add(self._ArcadeCamera__onRecreateDevice)
    self._ArcadeCamera__updateAdvancedCollision()
    self._ArcadeCamera__updateLodBiasForTanks()


@overrideIn(SniperCamera)
def enable(func, self, targetPos, saveZoom):
    self._SniperCamera__prevTime = BigWorld.time()
    player = BigWorld.player()
    if SniperCamera._SNIPER_ZOOM_LEVEL == -1:
        if saveZoom:
            self._SniperCamera__zoom = self._cfg['zoom']
        else:
            self._cfg['zoom'] = self._SniperCamera__zoom = self._cfg['zooms'][0]
    elif len(self._cfg['zooms']) > SniperCamera._SNIPER_ZOOM_LEVEL + 1:
        self._SniperCamera__zoom = self._cfg['zooms'][SniperCamera._SNIPER_ZOOM_LEVEL + 1]
    else:
        _logger.warning('zooms should always have enough length to use _SNIPER_ZOOM_LEVEL, using default now')
        self._cfg['zoom'] = self._SniperCamera__zoom = self._cfg['zooms'][0]
    self._SniperCamera__applyZoom(self._SniperCamera__zoom)
    self._SniperCamera__setupCamera(targetPos)
    vehicle = player.getVehicleAttached()
    if self._SniperCamera__waitVehicleCallbackId is not None:
        BigWorld.cancelCallback(self._SniperCamera__waitVehicleCallbackId)
    if vehicle is None:
        self._SniperCamera__waitVehicleCallbackId = BigWorld.callback(0.1, self._SniperCamera__waitVehicle)
    else:
        self._SniperCamera__showVehicle(False)
    BigWorld.camera(self._SniperCamera__cam)
    if self._SniperCamera__cameraUpdate(False) >= 0.0:
        self.delayCallback(0.0, self._SniperCamera__cameraUpdate)
    return


@overrideIn(SniperCamera)
def __getZooms(func, self):
    zooms = self._cfg['zooms']
    if not self._cfg['increasedZoom']:
        zooms = zooms[:4]
    return zooms


@overrideIn(CrosshairPanelContainer, condition=isClientLesta)
def setZoom(func, self, zoomFactor):
    if zoomFactor == self._CrosshairPanelContainer__zoomFactor:
        return
    self._CrosshairPanelContainer__zoomFactor = zoomFactor
    if zoomFactor >= 1:
        zoomString = i18n.makeString(INGAME_GUI.AIM_ZOOM, zoom=zoomFactor)
    else:
        zoomString = ''
    self.as_setZoomS(zoomString)


@overrideIn(CrosshairPanelContainer, condition=isClientWG)
def setZoom(func, self, zoomFactor):
    if zoomFactor == self._CrosshairPanelContainer__zoomFactor:
        return
    self._CrosshairPanelContainer__zoomFactor = zoomFactor
    if zoomFactor >= 1:
        zoomString = i18n.makeString(INGAME_GUI.AIM_ZOOM, zoom=zoomFactor)
    else:
        zoomString = ''
    self.as_setZoomS(zoomString, zoomFactor)