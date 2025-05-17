import Math, BattleReplay, BigWorld, constants
from Math import Matrix
from account_helpers.settings_core.settings_constants import GAME
from AvatarInputHandler.DynamicCameras.ArcadeCamera import ArcadeCamera

def overrideIn(cls, condition=lambda : True):

    def _overrideMethod(func):
        if not condition():
            return func
        funcName = func.__name__
        if funcName.startswith('__'):
            prefix = '_' if not cls.__name__.startswith('_') else ''
            funcName = prefix + cls.__name__ + funcName
        old = getattr(cls, funcName)

        def wrapper(*args, **kwargs):
            return func(old, *args, **kwargs)

        setattr(cls, funcName, wrapper)
        return wrapper

    return _overrideMethod


@overrideIn(ArcadeCamera)
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
        if self._ArcadeCamera__compareCurrStateSettingsKey(GAME.COMMANDER_CAM) or arcadeState is not None:
            state = None
            newCameraDistance = self._cfg['distRange'].max
            if arcadeState is not None:
                self._ArcadeCamera__zoomStateSwitcher.switchToState(arcadeState.zoomSwitcherState)
                state = self._ArcadeCamera__zoomStateSwitcher.getCurrentState()
                newCameraDistance = arcadeState.camDist
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
