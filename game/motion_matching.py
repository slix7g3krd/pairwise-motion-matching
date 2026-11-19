"""第 54 批：动作匹配（motion matching）修复。

针对角色走跑切换脚底打滑、急停滑步、转身穿模等问题，修复十个缺陷：

1. 时间归一采样（sample_time）：动作库不再按帧索引，而是按归一化时间索引，
   不同帧率的动画可在同一时间轴上对齐；
2. 轨迹+姿态特征（trajectory_features）：特征向量同时包含速度与朝向，
   不再只看速度；
3. 自适应权重（adaptive_weight）：代价函数权重按通道置信度缩放，
   不再使用固定权重；
4. 连续性惩罚（continuity_penalty）：候选搜索对相邻状态跳变施加惩罚，
   最近邻不再无视时间连续性；
5. 时间窗口（blend_window）：混合窗口以秒定义再换算为帧数，
   不再写死帧数；
6. 根运动剥离（strip_root_motion）：匹配前扣除根位移增量，
   避免根运动污染姿态特征；
7. 转身过渡（turn_transition）：每帧转身角度被限制，
   不再向目标朝向硬切；
8. 地面高度（ground_height）：地面高度差作为匹配量参与代价计算；
9. 骨架重定向（retarget_scale）：按骨架高度比缩放，
   不同骨架的动作可复用；
10. 帧率无关（frame_independent）：混合量按 dt × rate 计算，
    帧率波动不再导致选动作跳变。
"""


def sample_time(frame, fps):
    """按帧率返回归一化时间（时间归一采样）。

    :param frame: 帧索引（从 0 开始）
    :param fps: 采样帧率（帧/秒），必须为正
    :return: 该帧对应的归一化时间（秒），frame 0 恒为 0.0
    """
    if fps <= 0:
        raise ValueError("fps 必须为正数")
    return frame / fps


def trajectory_features(speed, direction):
    """返回轨迹与朝向特征（速度 + 朝向二维向量拼接）。

    :param speed: 标量速度
    :param direction: 朝向单位向量 (x, y)
    :return: 特征元组 (speed, direction_x, direction_y)
    """
    direction_x, direction_y = direction
    return (speed, direction_x, direction_y)


def adaptive_weight(error, confidence):
    """按置信度调整匹配权重（自适应权重）。

    权重 = 基础误差 × 通道置信度：置信度低的通道在代价函数中
    自动降权，置信度为 0 时该通道不参与匹配。

    :param error: 该通道的基础误差/基础权重
    :param confidence: 通道置信度，取值 [0.0, 1.0]
    :return: 调整后的权重
    """
    return error * confidence


def continuity_penalty(previous, next):
    """返回动作连续性惩罚。

    惩罚取相邻两个匹配状态之差的绝对值，差得越远（跳帧/滑步）
    惩罚越大，用于在最近邻搜索中压制不连续候选。

    :param previous: 上一状态的特征值
    :param next: 候选下一状态的特征值
    :return: 非负的连续性惩罚
    """
    return abs(next - previous)


def blend_window(fps, seconds):
    """按时间返回混合窗口（时间窗口，单位由秒换算为帧）。

    窗口时长以秒定义，与动作库帧率解耦；换帧率时窗口物理时长不变。

    :param fps: 当前帧率（帧/秒），必须为正
    :param seconds: 窗口时长（秒），必须非负
    :return: 窗口对应的帧数
    """
    if fps <= 0:
        raise ValueError("fps 必须为正数")
    if seconds < 0:
        raise ValueError("窗口时长不能为负")
    return fps * seconds


def strip_root_motion(root, delta):
    """剥离根运动位移。

    从根节点位置中逐分量扣除根运动增量，得到与根平移无关的
    局部姿态位置，使匹配基于姿态而非角色在世界中的位移。

    :param root: 根节点位置元组，如 (x, y)
    :param delta: 本帧根运动增量元组，形状与 root 一致
    :return: 剥离根运动后的位置元组
    """
    return tuple(component - offset for component, offset in zip(root, delta))


def turn_transition(angle, max_turn):
    """限制转身过渡角。

    将目标转身角钳制在 [-max_turn, max_turn] 内，避免一帧硬切到
    目标朝向造成穿模；剩余角度在后续帧继续转。

    :param angle: 期望转身角（弧度）
    :param max_turn: 单帧允许的最大转身角（弧度），必须非负
    :return: 钳制后的实际转身角
    """
    if max_turn < 0:
        raise ValueError("max_turn 不能为负")
    return max(-max_turn, min(angle, max_turn))


def ground_height(height, target):
    """返回地面高度差。

    :param height: 当前/候选姿态的脚部地面高度
    :param target: 目标地面高度
    :return: 高度差，正值表示候选高于目标
    """
    return height - target


def retarget_scale(source_height, target_height):
    """返回骨架重定向缩放比。

    缩放比 = 目标骨架高度 / 源骨架高度，源动作的位移与肢体长度
    按该比例缩放后即可重定向到不同骨架。

    :param source_height: 源骨架高度，必须为正
    :param target_height: 目标骨架高度，必须为正
    :return: 重定向缩放比，两骨架等高时为 1.0
    """
    if source_height <= 0:
        raise ValueError("source_height 必须为正数")
    return target_height / source_height


def frame_independent(dt, rate):
    """返回与帧率无关的混合量。

    混合量 = 帧间隔 dt × 变化率 rate：同一物理时长下无论帧率如何
    波动，累计混合量一致，避免帧率抖动导致选动作跳变。

    :param dt: 本帧帧间隔（秒）
    :param rate: 目标变化率（每秒）
    :return: 本帧应施加的混合量
    """
    return dt * rate
