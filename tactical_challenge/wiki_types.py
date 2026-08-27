from dataclasses import dataclass


@dataclass(frozen=True)
class StudentIcon:
    """生徒の正式名称と攻略Wiki上のアイコンURL。"""

    name: str
    image_url: str
