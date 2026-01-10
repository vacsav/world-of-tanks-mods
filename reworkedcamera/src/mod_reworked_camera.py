import Math, math_utils, BigWorld, BattleReplay, constants, logging
from Math import Matrix
from realm import CURRENT_REALM
from AvatarInputHandler.DynamicCameras.ArcadeCamera import ArcadeCamera, ENABLE_INPUT_ROTATION_INERTIA, _COLLIDE_ANIM_DIST, _COLLIDE_ANIM_INTERVAL
from AvatarInputHandler.DynamicCameras.SniperCamera import SniperCamera
from AvatarInputHandler.DynamicCameras.arcade_camera_helper import EScrollDir
from account_helpers.settings_core.settings_constants import GAME
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


orig_init = ArcadeCamera.__init__
def mod_init(self, *args, **kwargs):
    orig_init(self, *args, **kwargs)
    self.__lastLodBias = None
ArcadeCamera.__init__ = mod_init


@overrideIn(ArcadeCamera, condition=isClientLesta)
def enable(func, self, preferredPos=None, closesDist=False, postmortemParams=None, turretYaw=None, gunPitch=None, camTransitionParams=None, initialVehicleMatrix=None, arcadeState=None):
    replayCtrl = BattleReplay.g_replayCtrl
    if replayCtrl.isRecording:
        replayCtrl.setAimClipPosition(self._ArcadeCamera__aimOffset)
    self.measureDeltaTime()
    player = BigWorld.player()
    vehicle = player.getVehicleAttached()
    if player.observerSeesAll() and player.arena.period == constants.ARENA_PERIOD.BATTLE and vehicle and vehicle.id == player.playerVehicleID:
        self.delayCallback(0.0, self.enable, preferredPos, closesDist, postmortemParams, turretYaw, gunPitch, camTransitionParams, initialVehicleMatrix)
        return
    else:
        if initialVehicleMatrix is None:
            initialVehicleMatrix = player.getOwnVehicleMatrix(Math.Matrix(self.vehicleMProv)) if vehicle is None else vehicle.matrix
        vehicleMProv = initialVehicleMatrix
        isCommanderCam = self._ArcadeCamera__compareCurrStateSettingsKey(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM)
        isArcadeCam = self._ArcadeCamera__isInArcadeZoomState()
        if isCommanderCam or arcadeState is not None or isArcadeCam:
            if isCommanderCam:
                state = None
                newCameraDistance = 25
            elif arcadeState is not None:
                self._ArcadeCamera__zoomStateSwitcher.switchToState(arcadeState.zoomSwitcherState)
                state = self._ArcadeCamera__zoomStateSwitcher.getCurrentState()
                newCameraDistance = arcadeState.camDist
            else:
                currentDist = self._ArcadeCamera__aimingSystem.distanceFromFocus
                state = None
                newCameraDistance = min(currentDist, 25)
            self._ArcadeCamera__updateProperties(state=state)
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
        return


@overrideIn(ArcadeCamera, condition=isClientLesta) 
def __update(func, self, dx, dy, dz, rotateMode = True, zoomMode = True):
    if self._ArcadeCamera__aimingSystem:
        eScrollDir = EScrollDir.convertDZ(dz)
        prevPos = self._ArcadeCamera__inputInertia.calcWorldPos(self._ArcadeCamera__aimingSystem.matrixProvider)
        prevDist = self._ArcadeCamera__aimingSystem.distanceFromFocus
        distMinMax = self._ArcadeCamera__distRange
        if self._ArcadeCamera__isCamInTransition:
            self._ArcadeCamera__isCamInTransition = self._ArcadeCamera__cameraTransition.isInTransition()
        isColliding = self._ArcadeCamera__cam.hasCollision()
        collisionWhileGlide = False
        isCommanderCam = self._ArcadeCamera__compareCurrStateSettingsKey(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM)
        isArcadeCam = self._ArcadeCamera__isInArcadeZoomState()
        commanderCam = self._ArcadeCamera__isSettingsEnabled(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__isSettingsEnabled(GAME.COMMANDER_CAM)
        if self._ArcadeCamera__inputInertia.isGliding() and not isColliding and eScrollDir is EScrollDir.OUT and not isCommanderCam:
            cameraPos = self._ArcadeCamera__aimingSystem.matrix.translation
            collisionWhileGlide = self._ArcadeCamera__cam.isColliding(BigWorld.player().spaceID, cameraPos)
        preventScrollOut = (isColliding or collisionWhileGlide) and (eScrollDir is EScrollDir.OUT) and (not isCommanderCam)
        if preventScrollOut and prevDist == distMinMax.max and commanderCam and isArcadeCam:
            preventScrollOut = False
        if isColliding and eScrollDir is EScrollDir.OUT:
            self._ArcadeCamera__collideAnimatorEasing.start(_COLLIDE_ANIM_DIST, _COLLIDE_ANIM_INTERVAL)
        distChanged = False
        if zoomMode and eScrollDir and not self._ArcadeCamera__overScrollProtector.isProtecting() and not preventScrollOut:
            if eScrollDir is EScrollDir.OUT and not self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM) and self._ArcadeCamera__isSettingsEnabled(GAME.COMMANDER_CAM):
                event_dispatcher.showCommanderCamHint(show = True)
            distDelta = dz * float(self._ArcadeCamera__curScrollSense)
            newDist = math_utils.clamp(distMinMax.min, distMinMax.max, prevDist - distDelta)
            floatEps = 0.001
            if abs(newDist - prevDist) > floatEps:
                self._ArcadeCamera__updateCameraSettings(newDist)
                self._ArcadeCamera__inputInertia.glideFov(self._ArcadeCamera__calcRelativeDist())
                self._ArcadeCamera__aimingSystem.aimMatrix = self._ArcadeCamera__calcAimMatrix()
                distChanged = True
            if distChanged:
                self._ArcadeCamera__updateLodBiasForTanks()
            if abs(newDist - prevDist) < floatEps and math_utils.almostZero(newDist - distMinMax.min):
                if self._ArcadeCamera__isInArcadeZoomState() and self._ArcadeCamera__onChangeControlMode and not self._ArcadeCamera__updatedByKeyboard:
                    self._ArcadeCamera__onChangeControlMode()
                    return
                else:
                    self._ArcadeCamera__changeZoomState(EScrollDir.IN)
            elif abs(newDist - prevDist) < floatEps and math_utils.almostZero(newDist - distMinMax.max):
                self._ArcadeCamera__changeZoomState(EScrollDir.OUT)
        if rotateMode and not self._ArcadeCamera__isCamInTransition:
            self._ArcadeCamera__updateAngles(dx, dy)
        if ENABLE_INPUT_ROTATION_INERTIA and not distChanged:
            self._ArcadeCamera__aimingSystem.update(0.0)
        if ENABLE_INPUT_ROTATION_INERTIA or distChanged:
            self._ArcadeCamera__startInputInertiaTransition(prevPos)
        return
    else:
        return


@overrideIn(ArcadeCamera, condition=isClientWG)
def enable(func, self, preferredPos = None, closesDist = False, postmortemParams = None, turretYaw = None, gunPitch = None, camTransitionParams = None, initialVehicleMatrix = None, arcadeState = None):
    replayCtrl = BattleReplay.g_replayCtrl
    if replayCtrl.isRecording:
        replayCtrl.setAimClipPosition(self._aimOffset)
    self.measureDeltaTime()
    player = BigWorld.player()
    attachedVehicle = player.getVehicleAttached()
    newVehicleID = camTransitionParams.get('newVehicleID', 0) if camTransitionParams else 0
    if newVehicleID:
        vehicle = BigWorld.entity(newVehicleID)
        isWaitingForVehicle = vehicle is None
    else:
        vehicle = attachedVehicle
        isWaitingForVehicle = False
    isPlayerVehicleAttached = attachedVehicle.id == player.playerVehicleID if attachedVehicle else False
    isObserverInBattle = player.observerSeesAll() and (player.arena.period == constants.ARENA_PERIOD.BATTLE)
    if (isObserverInBattle and isPlayerVehicleAttached) or isWaitingForVehicle:
        self.delayCallback(0.0, self.enable, preferredPos, closesDist, postmortemParams, turretYaw, gunPitch, camTransitionParams, initialVehicleMatrix)
        return
    else:
        if initialVehicleMatrix is None:
            initialVehicleMatrix = player.getOwnVehicleMatrix(Math.Matrix(self.vehicleMProv)) if vehicle is None else vehicle.matrix
        vehicleMProv = initialVehicleMatrix
        isCommanderCam = self._ArcadeCamera__compareCurrStateSettingsKey(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM)
        isArcadeCam = self.isInArcadeZoomState()
        if isCommanderCam or arcadeState is not None or isArcadeCam:
            if isCommanderCam:
                state = None
                newCameraDistance = 25
            elif arcadeState is not None:
                self._ArcadeCamera__zoomStateSwitcher.switchToState(arcadeState.zoomSwitcherState)
                state = self._ArcadeCamera__zoomStateSwitcher.getCurrentState()
                newCameraDistance = arcadeState.camDist
            else:
                currentDist = self._ArcadeCamera__aimingSystem.distanceFromFocus
                state = None
                newCameraDistance = min(currentDist, 25)
            self._updateProperties(state = state)
            self._updateCameraSettings(newCameraDistance)
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
                camDist = self._distRange.max
        elif closesDist:
            camDist = self._distRange.min
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
        self._setDynamicCollisions(True)
        self._ArcadeCamera__aimingSystem.enable(preferredPos, turretYaw, gunPitch)
        self._ArcadeCamera__aimingSystem.aimMatrix = self._ArcadeCamera__calcAimMatrix()
        if camTransitionParams is not None and BigWorld.camera() is not self._ArcadeCamera__cam:
            pivotSettings = camTransitionParams.get('pivotSettings', None)
            if pivotSettings is not None:
                self._ArcadeCamera__aimingSystem.setPivotSettings(pivotSettings[0], pivotSettings[1])
            cameraTransitionDuration = camTransitionParams.get('cameraTransitionDuration', -1)
            hasTransitionCamera = cameraTransitionDuration > 0
            keepRotation = hasTransitionCamera or camTransitionParams.get('keepRotation', False)
            if keepRotation:
                distanceFromFocus = camTransitionParams.get('distanceFromFocus', None)
                self._ArcadeCamera__keepCameraOrientation(distanceFromFocus)
            if hasTransitionCamera:
                self._ArcadeCamera__setupCameraTransition(cameraTransitionDuration)
        self._cameraUpdate()
        self.delayCallback(0.0, self._cameraUpdate)
        if not self._ArcadeCamera__isCamInTransition:
            if self._ArcadeCamera__postmortemMode:
                self.delayCallback(0.0, self._ArcadeCamera__setCamera)
            else:
                self._ArcadeCamera__setCamera()
        from gui import g_guiResetters
        g_guiResetters.add(self._ArcadeCamera__onRecreateDevice)
        self._ArcadeCamera__updateAdvancedCollision()
        self._ArcadeCamera__updateLodBiasForTanks()
        return


@overrideIn(ArcadeCamera, condition=isClientWG)
def __update(func, self, dx, dy, dz, rotateMode = True, zoomMode = True):
    if self._ArcadeCamera__aimingSystem:
        eScrollDir = EScrollDir.convertDZ(dz)
        prevPos = self._ArcadeCamera__inputInertia.calcWorldPos(self._ArcadeCamera__aimingSystem.matrixProvider)
        prevDist = self._ArcadeCamera__aimingSystem.distanceFromFocus
        distMinMax = self._distRange
        if self._ArcadeCamera__isCamInTransition:
            self._ArcadeCamera__isCamInTransition = self._ArcadeCamera__cameraTransition.isInTransition()
        isColliding = self._ArcadeCamera__cam.hasCollision()
        collisionWhileGlide = False
        isCommanderCam = self._ArcadeCamera__compareCurrStateSettingsKey(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM)
        isArcadeCam = self.isInArcadeZoomState()
        commanderCam = self._ArcadeCamera__isSettingsEnabled(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__isSettingsEnabled(GAME.COMMANDER_CAM)
        if self._ArcadeCamera__inputInertia.isGliding() and not isColliding and eScrollDir is EScrollDir.OUT and not isCommanderCam:
            cameraPos = self._ArcadeCamera__aimingSystem.matrix.translation
            collisionWhileGlide = self._ArcadeCamera__cam.isColliding(BigWorld.player().spaceID, cameraPos)
        preventScrollOut = (isColliding or collisionWhileGlide) and (eScrollDir is EScrollDir.OUT) and (not isCommanderCam)
        if preventScrollOut and prevDist == distMinMax.max and commanderCam and self.isInArcadeZoomState():        
            preventScrollOut = False
        if isColliding and eScrollDir is EScrollDir.OUT:
            self._ArcadeCamera__collideAnimatorEasing.start(_COLLIDE_ANIM_DIST, _COLLIDE_ANIM_INTERVAL)
        distChanged = False
        if zoomMode and eScrollDir and not self._ArcadeCamera__overScrollProtector.isProtecting() and not preventScrollOut:
            if eScrollDir is EScrollDir.OUT and not self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM) and self._ArcadeCamera__isSettingsEnabled(GAME.COMMANDER_CAM) and not self._ArcadeCamera__postmortemMode:
                event_dispatcher.showCommanderCamHint(show = True)
            distDelta = dz * float(self._ArcadeCamera__curScrollSense)
            newDist = math_utils.clamp(distMinMax.min, distMinMax.max, prevDist - distDelta)
            floatEps = 0.001
            if abs(newDist - prevDist) > floatEps:
                self._updateCameraSettings(newDist)
                self._ArcadeCamera__inputInertia.glideFov(self._ArcadeCamera__calcRelativeDist())
                self._ArcadeCamera__aimingSystem.aimMatrix = self._ArcadeCamera__calcAimMatrix()
                distChanged = True
            if distChanged:
                self._ArcadeCamera__updateLodBiasForTanks()
            if abs(newDist - prevDist) < floatEps and math_utils.almostZero(newDist - distMinMax.min):
                if self.isInArcadeZoomState() and self._ArcadeCamera__onChangeControlMode and not self._ArcadeCamera__updatedByKeyboard:
                    self._ArcadeCamera__onChangeControlMode()
                    return
                else:
                    self._ArcadeCamera__changeZoomState(EScrollDir.IN)
            elif abs(newDist - prevDist) < floatEps and math_utils.almostZero(newDist - distMinMax.max):
                self._ArcadeCamera__changeZoomState(EScrollDir.OUT)
        if rotateMode and not self._ArcadeCamera__isCamInTransition:
            self._ArcadeCamera__updateAngles(dx, dy)
        if ENABLE_INPUT_ROTATION_INERTIA and not distChanged:
            self._ArcadeCamera__aimingSystem.update(0.0)
        if ENABLE_INPUT_ROTATION_INERTIA or distChanged:
            self._ArcadeCamera__startInputInertiaTransition(prevPos)
        return
    else:
        return


@overrideIn(ArcadeCamera)
def __updateAdvancedCollision(func, self):
    isCommanderCam = self._ArcadeCamera__compareCurrStateSettingsKey(GAME.PRE_COMMANDER_CAM) or self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM)
    self._ArcadeCamera__cam.setCollisionCheckOnlyAtPos(isCommanderCam)
    self._ArcadeCamera__aimingSystem.cursorShouldCheckCollisions(not isCommanderCam)


@overrideIn(ArcadeCamera)
def __updateLodBiasForTanks(func, self):
    aimingSystem = getattr(self, "_ArcadeCamera__aimingSystem", None)
    currentDist = aimingSystem.distanceFromFocus if aimingSystem else 5.0
    state = self._ArcadeCamera__zoomStateSwitcher.getCurrentState()
    if isClientWG():
        isArcadeCam = self.isInArcadeZoomState()
    else:
        isArcadeCam = self._ArcadeCamera__isInArcadeZoomState()
    if state:
        lod = state.minLODBiasForTanks
    elif isArcadeCam and currentDist > 25.0:
        lod = 1.6
    else:
        lod = 0.0
    if getattr(self, "__lastLodBias", None) != lod:
        BigWorld.setMinLodBiasForTanks(lod)
        self.__lastLodBias = lod


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