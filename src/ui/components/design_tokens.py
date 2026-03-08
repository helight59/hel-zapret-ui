from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UiTokens:
    app_bg: str = '#f2f3f5'
    panel_bg: str = '#ffffff'
    panel_bg_soft: str = '#f6f7f8'
    panel_bg_hover: str = '#eef1f5'
    panel_bg_active: str = '#e8ecf2'
    text_primary: str = '#2c2d2e'
    text_muted: str = '#5f6b7a'
    text_disabled: str = '#7b8897'
    border: str = '#dce4ee'
    border_soft: str = '#e5ebf1'
    border_active: str = '#2688eb'
    primary: str = '#2688eb'
    primary_hover: str = '#1f7fe0'
    primary_pressed: str = '#1b72ca'
    danger: str = '#e64646'
    danger_hover: str = '#db3f3f'
    danger_pressed: str = '#c93838'
    warning: str = '#f59e0b'
    shadow_alpha: int = 28
    radius_s: int = 8
    radius_m: int = 12
    radius_round: int = 14
    font_size_sm: int = 12
    font_size_base: int = 13
    font_size_title: int = 18
    space_xs: int = 4
    space_s: int = 8
    space_m: int = 12
    space_l: int = 16
    space_xl: int = 24
    control_height_xs: int = 22
    control_height_s: int = 26
    control_height_m: int = 30
    control_height_l: int = 27
    control_height_xl: int = 41
    busy_strip_height: int = 4
    busy_indicator_height: int = 2
    sidebar_open_width: int = 216
    sidebar_closed_width: int = 58
    card_shadow_blur: int = 18
    card_shadow_y: int = 6


TOKENS = UiTokens()
