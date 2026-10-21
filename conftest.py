# pytest kök dizini repo köküdür; "import engine" bu sayede çalışır.
# Testler kullanıcının veri paketlerinden (%APPDATA%\CarbonDelta\veri) etkilenmesin:
# her oturum boş bir geçici veri klasörüyle başlar.
import os
import tempfile

_EMPTY = tempfile.mkdtemp(prefix="carbondelta_test_veri_")
os.environ["CARBONDELTA_DATA_DIR"] = _EMPTY
os.environ["CARBONDELTA_TEST_EMPTY_DIR"] = _EMPTY
# Kullanıcının uygulamada kaydettiği Delti anahtarı testlere karışmasın.
os.environ["CARBONDELTA_SETTINGS_DIR"] = tempfile.mkdtemp(prefix="carbondelta_test_ayar_")
