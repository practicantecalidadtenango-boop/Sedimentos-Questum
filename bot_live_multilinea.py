import os
import time
import shutil
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from github import Github

# ==========================================
# 1. CARGA DE CREDENCIALES
# ==========================================
load_dotenv()
USUARIO = os.getenv("USER_PORTAL")
PASSWORD = os.getenv("PASS_PORTAL")
TOKEN_GITHUB = os.getenv("GITHUB_TOKEN")
REPO_GITHUB = os.getenv("GITHUB_REPO")

# ==========================================
# 2. CONFIGURACIÓN LIVE Y RUTAS
# ==========================================
LINEAS_A_MONITOREAR = [
    {"linea": "Línea 6 (GM)", "maquina": "SEDIMENTOS", "producto": "GM_GENV", "hoja": "OP. 190_1"},
    {"linea": "Línea 6 (GM)", "maquina": "SEDIMENTOS", "producto": "GM_GENV", "hoja": "OP. 190_2"},
]

INTERVALO_REPETICION = 1800 

RUTA_BASE = r"C:\Users\mcxgtovar\Documents\Sedimentos"
RUTA_LIVE_DESCARGAS = os.path.join(RUTA_BASE, "DescargasLive")
RUTA_BD_LIVE = os.path.join(RUTA_BASE, "BD_LECTURAS_LIVE.xlsx")
RUTA_RESPALDOS = os.path.join(RUTA_BASE, "Respaldos_Excels")

for r in [RUTA_LIVE_DESCARGAS, RUTA_RESPALDOS]:
    if not os.path.exists(r): os.makedirs(r)

def log(mensaje):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {mensaje}")

# ==========================================
# 3. FUNCIÓN PARA CARGAR A GITHUB
# ==========================================
def subir_a_github(ruta_local):
    try:
        log("☁️ Sincronizando con GitHub...")
        g = Github(TOKEN_GITHUB)
        repo = g.get_repo(REPO_GITHUB)
        with open(ruta_local, 'rb') as f:
            content = f.read()
        nombre_archivo_repo = os.path.basename(ruta_local)
        try:
            contents = repo.get_contents(nombre_archivo_repo, ref="main")
            repo.update_file(contents.path, f"Update SPC {datetime.now().strftime('%H:%M')}", content, contents.sha, branch="main")
            log(f"✅ GitHub Actualizado.")
        except:
            repo.create_file(nombre_archivo_repo, f"Initial SPC {datetime.now().strftime('%H:%M')}", content, branch="main")
            log(f"✅ Archivo creado en GitHub.")
    except Exception as e:
        log(f"❌ Error GitHub: {e}")

# ==========================================
# 4. PROCESADOR DE DATOS (ELIMINACIÓN DE DUPLICADOS PULIDA)
# ==========================================
def procesar_datos_live(ruta, config):
    try:
        log(f"📊 Procesando descarga: {config['hoja']}...")
        df_raw = pd.read_excel(ruta, sheet_name='Información Completa', header=None)
        
        # Localizar cabecera real
        fila_tabla = None
        for i, row in df_raw.iterrows():
            valores = [str(x).strip() for x in row.values if pd.notna(x)]
            if 'N° Medición' in valores or 'Fecha y hora' in valores:
                fila_tabla = i
                break
        
        if fila_tabla is None:
            log("❌ Error: Cabecera no encontrada.")
            return

        # Limpiar datos descargados
        df_new = pd.read_excel(ruta, sheet_name='Información Completa', header=fila_tabla)
        df_new.columns = [str(c).strip() for c in df_new.columns]
        df_new = df_new.dropna(how='all')

        # Insertar metadatos del Bot
        df_new.insert(0, 'Bot_Fecha', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        df_new.insert(1, 'Bot_Hoja', config['hoja'])
        df_new.insert(2, 'Bot_Linea', config['linea'])

        # --- LÓGICA DE DUPLICADOS ---
        if os.path.exists(RUTA_BD_LIVE):
            df_maestra = pd.read_excel(RUTA_BD_LIVE)
            
            # Unimos lo viejo con lo nuevo
            df_maestra = pd.concat([df_maestra, df_new], ignore_index=True)
            
            # Definimos las columnas que identifican una medición única.
            # Ignoramos 'Bot_Fecha' para que el bot no crea que son datos nuevos solo por la hora.
            columnas_identificadoras = [c for c in df_maestra.columns if c != 'Bot_Fecha']
            
            # Eliminamos duplicados evaluando todo el contenido excepto la fecha del bot
            total_antes = len(df_maestra)
            df_maestra = df_maestra.drop_duplicates(subset=columnas_identificadoras, keep='first')
            total_despues = len(df_maestra)
            
            log(f"♻️ Limpieza: Se eliminaron {total_antes - total_despues} filas duplicadas.")
        else:
            df_maestra = df_new

        # Guardar y subir
        df_maestra.to_excel(RUTA_BD_LIVE, index=False)
        log(f"✨ BD Local lista ({len(df_maestra)} registros).")
        subir_a_github(RUTA_BD_LIVE)
        
    except Exception as e:
        log(f"❌ Error en procesador: {e}")

# ==========================================
# 5. CICLO DE NAVEGACIÓN (SIN CAMBIOS)
# ==========================================
def ejecutar_ciclo_completo():
    hoy = datetime.now().strftime("%Y-%m-%dT00:00")
    ahora = datetime.now().strftime("%Y-%m-%dT%H:%M")
    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--start-maximized")
    prefs = {"download.default_directory": RUTA_LIVE_DESCARGAS, "download.prompt_for_download": False}
    opciones.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=opciones)
    wait = WebDriverWait(driver, 60)

    try:
        log("🔑 Iniciando sesión...")
        driver.get("https://qam-transferspc.questum.net/")
        wait.until(EC.presence_of_element_located((By.ID, "UserName"))).send_keys(USUARIO)
        driver.find_element(By.ID, "pass").send_keys(PASSWORD)
        driver.find_element(By.ID, "pass").send_keys(Keys.ENTER)
        time.sleep(5)

        for config in LINEAS_A_MONITOREAR:
            try:
                log(f"--- Línea: {config['linea']} | {config['hoja']} ---")
                driver.get("https://qam-transferspc.questum.net/Analisis/ViewLastResultsFilter")
                time.sleep(6)

                for campo, valor in [('sltStations', config['linea']), ('sltMachines', config['maquina']), ('sltProducts', config['producto'])]:
                    driver.execute_script(f"var s=$('#{campo}')[0]; for(var i=0;i<s.options.length;i++){{if(s.options[i].text.toUpperCase().includes('{valor}'.toUpperCase())){{s.selectedIndex=i; $(s).trigger('change'); break;}}}}")
                    time.sleep(4)
                    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "blockUI")))

                log("🎯 Capturando...")
                xpath_cap = f"//div[@role='row'][.//div[contains(text(), '{config['hoja']}')]]//button"
                btn_cap = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cap)))
                driver.execute_script("$(arguments[0]).click();", btn_cap)
                
                v_base = driver.current_window_handle
                nueva_v = None
                for _ in range(15):
                    if len(driver.window_handles) > 1:
                        nueva_v = [h for h in driver.window_handles if h != v_base][0]
                        break
                    time.sleep(1)

                if nueva_v:
                    driver.switch_to.window(nueva_v)
                    driver.maximize_window()
                    time.sleep(5)
                    driver.execute_script("$('#MenuForLinks').click();")
                    time.sleep(2)
                    driver.find_element(By.ID, "linkReports").click()
                    time.sleep(8)
                    
                    # Marcar variables
                    driver.execute_script("""
                        var chkAll = document.querySelector('.ag-header-cell .ag-checkbox-wrapper');
                        if (chkAll) chkAll.click();
                        document.querySelectorAll('.ag-checkbox-input').forEach(chk => { if(!chk.checked) chk.click(); });
                    """)
                    time.sleep(3)
                    
                    # Filtrar
                    driver.execute_script(f"$('#inpDateSince').val('{hoy}'); $('#inpDateTo').val('{ahora}').trigger('change');")
                    time.sleep(2)
                    driver.execute_script("document.querySelectorAll('button').forEach(b => { if(b.innerText.includes('Filtrar')) b.click(); })")
                    
                    time.sleep(30)
                    wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "blockUI")))
                    
                    # Descargar
                    antes = set(os.listdir(RUTA_LIVE_DESCARGAS))
                    driver.execute_script("""
                        var chk = $('#gridExportExcel input[type="checkbox"]');
                        if(chk.length > 0) chk.prop('checked', true).trigger('change').trigger('click');
                        exportReport(true, 2);
                    """)
                    
                    for _ in range(50):
                        driver.execute_script("if($('.swal2-confirm').length) { $('.swal2-confirm').click(); }")
                        xlsx = [f for f in (set(os.listdir(RUTA_LIVE_DESCARGAS)) - antes) if f.endswith(".xlsx")]
                        if xlsx:
                            ruta_desc = os.path.join(RUTA_LIVE_DESCARGAS, xlsx[0])
                            time.sleep(4)
                            procesar_datos_live(ruta_desc, config)
                            res = f"{config['hoja'].replace(' ','_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                            shutil.move(ruta_desc, os.path.join(RUTA_RESPALDOS, res))
                            break
                        time.sleep(2)

                    driver.close()
                    driver.switch_to.window(v_base)
            except Exception as e:
                log(f"⚠️ Error en ciclo: {e}")
                while len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-1]); driver.close()
                driver.switch_to.window(driver.window_handles[0])

        log("✅ Ciclo finalizado.")
    except Exception as e:
        log(f"❌ Error crítico: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    log("🚀 INICIANDO BOT SPC LIVE...")
    while True:
        ejecutar_ciclo_completo()
        log(f"💤 Esperando 30 min...")
        time.sleep(INTERVALO_REPETICION)
