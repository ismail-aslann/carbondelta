"""Uygulamanın adı ve kullanıcı klasörü tek yerde.

Deneme sürümü (karbondeltadeneme) yalnızca bu sabitleri değiştirir; böylece kendi
%APPDATA% klasörünü kullanır ve ana uygulamanın geçmişine/verilerine dokunmaz.
"""
from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "CarbonDelta Deneme"      # pencere başlığı, uygulama adı
USER_DIR_NAME = "CarbonDeltaDeneme"   # %APPDATA% altındaki klasör


def user_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / USER_DIR_NAME
