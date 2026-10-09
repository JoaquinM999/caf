import pytest
from pathlib import Path
import caf.tools as caf_tools
from unittest.mock import patch, MagicMock

def test_safe_resolve_valid():
    # Relative path should be safely resolved inside WORKSPACE_DIR
    target = caf_tools._safe_resolve("test.txt")
    assert str(caf_tools.WORKSPACE_DIR) in str(target)

def test_safe_resolve_path_traversal():
    with pytest.raises(ValueError, match="Acceso denegado"):
        caf_tools._safe_resolve("../fuera_de_workspace.txt")
        
    with pytest.raises(ValueError):
        caf_tools._safe_resolve("..\\fuera_de_workspace.txt")

def test_abrir_programa_no_permitido():
    res = caf_tools.abrir_programa("virus.exe")
    assert "no está en la lista blanca" in res

@patch("subprocess.run")
def test_abrir_programa_permitido(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="Éxito")
    res = caf_tools.abrir_programa("calculadora")
    assert "Éxito" in res

def test_crear_y_leer_archivo():
    res_crear = caf_tools.crear_archivo("prueba.txt", "Hola mundo")
    assert "Éxito" in res_crear
    
    res_leer = caf_tools.leer_archivo("prueba.txt")
    assert res_leer == "Hola mundo"
    
    # Cleanup
    caf_tools._safe_resolve("prueba.txt").unlink()

def test_borrar_sin_confirmacion():
    caf_tools.crear_archivo("borrar.txt", "Hola")
    res = caf_tools.borrar_archivo("borrar.txt", "no")
    assert "pendiente_confirmacion" in res
    assert caf_tools._safe_resolve("borrar.txt").exists()
    
def test_borrar_con_confirmacion():
    res = caf_tools.borrar_archivo("borrar.txt", "si")
    assert "Éxito" in res
    assert not caf_tools._safe_resolve("borrar.txt").exists()
