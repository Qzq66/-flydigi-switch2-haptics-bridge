"""Scene instructions and conservative UI arming reserve; no waveform controls."""
SCENES={
    'door':dict(prepare='停在门前并松开全部按键与摇杆',action='进门一次'),
    'dodge-attack':dict(prepare='停在可复现震动的战斗位置并松开全部按键与摇杆',action='短按下方B闪避，松开后短按右方A攻击，再全部松开'),
    'dodge-attack-repeat':dict(prepare='停在能重复两组B闪避→A攻击的同一战斗位置并全松',
        action='做第一组B闪避→松开→A攻击→全松；震动停止后至少等5秒，再做同样第二组并全松，只做两组',arm_reserve_seconds=20)
}

def scene_can_arm(scene,status,now):
    from bridge_game_phase import can_arm,remaining
    return can_arm(status,now) and remaining(status,now)>SCENES[scene].get('arm_reserve_seconds',0)
