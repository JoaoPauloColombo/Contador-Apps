import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
from tiktok_captcha_solver import SeleniumSolver
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
import subprocess
from datetime import datetime, timedelta
import socket
import threading
import os
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

file_lock = threading.Lock()

def convert_to_int(value):
    if 'K' in value:
        return int(float(value.replace('K', '')) * 1000)
    elif 'M' in value:
        return int(float(value.replace('M', '')) * 1000000)
    else:
        return int(value.replace(',', ''))

def is_within_days(date_str, days):
    now = datetime.now()
    if 'ago' in date_str:
        if 'm' in date_str: 
            minutes = int(date_str.split('m')[0])
            video_date = now - timedelta(minutes=minutes)
        elif 'h' in date_str:
            hours = int(date_str.split('h')[0])
            video_date = now - timedelta(hours=hours)
        elif 'd' in date_str:
            days_ago = int(date_str.split('d')[0])
            video_date = now - timedelta(days=days_ago)
        elif 'w' in date_str:
            weeks_ago = int(date_str.split('w')[0])
            video_date = now - timedelta(weeks=weeks_ago)
    else:
        try:
            video_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            video_date = datetime.strptime(date_str, '%m-%d')
            video_date = video_date.replace(year=now.year)
            if video_date > now:
                video_date = video_date.replace(year=now.year - 1)
    return (now - video_date).days <= days

def log_message(concurso, level, message, user="", error=None):
    """
    Registra mensagens em diferentes arquivos de log baseado no nível
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] "
    if user:
        log_entry += f"[{user}] "
    log_entry += message
    if error:
        log_entry += f"\nError: {str(error)}"

    log_files = {
        "ALERT": f"database/{concurso}/logs/tiktok/alerts.log",
        "ERROR": f"database/{concurso}/logs/tiktok/errors.log",
        "INFO": f"database/{concurso}/logs/tiktok/info.log",
        "CAPTCHA": f"database/{concurso}/logs/tiktok/captcha.log",
        "REMOVED": f"database/{concurso}/logs/tiktok/removedAccounts.log"
    }

    log_file = log_files.get(level, f"database/{concurso}/logs/tiktok/general.log")
    
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(log_entry + "\n")

def log_failed_user(concurso, user, reason):
    """
    Registra usuários que falharam durante o scraping
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(f"database/{concurso}/logs/tiktok/failed_users.log", "a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {user}: {reason}\n")

def registrar_captcha(usuario, sucesso, concurso):
    data_atual = datetime.now().strftime("%Y-%m-%d")
    hora_atual = datetime.now().strftime("%H:%M:%S")
    endereco_ip = socket.gethostbyname(socket.gethostname())
    status = "SUCESSO" if sucesso else "FALHA"
    detalhes = "COMPLETOU" if sucesso else "NÃO COMPLETOU"
    
    with open(f"database/{concurso}/logs/tiktok/captcha_verification.log", "a", encoding="utf-8") as file:
        file.write(f"Data da Verificação: {data_atual}\n")
        file.write(f"Usuário: {usuario}\n")
        file.write(f"Status do Captcha: {status}\n")
        file.write(f"Detalhes: O usuário {detalhes} a verificação do captcha com sucesso.\n")
        file.write(f"Horário: {hora_atual}\n")
        file.write(f"IP: {endereco_ip}\n")
        file.write("\n")

def solve_captcha(sadcaptcha, driver, usuario, concurso):
    log_message(concurso, "INFO", f"Tentando resolver o CAPTCHA", usuario)
    while True:
        try:
            if check_for_captcha(driver):
                sadcaptcha.solve_captcha_if_present()
                log_message(concurso, "CAPTCHA", f"CAPTCHA resolvido com sucesso", usuario)
                registrar_captcha(usuario, True, concurso)
                time.sleep(2) 
                return True
            else:
                log_message(concurso, "INFO", f"CAPTCHA não encontrado", usuario)
                return False
        except Exception as e:
            log_message(concurso, "ERROR", f"Tentativa de resolver o CAPTCHA falhou", usuario, e)
            log_failed_user(concurso, usuario, f"Falha no CAPTCHA: {str(e)}")
            registrar_captcha(usuario, False, concurso)
            time.sleep(30)
        registrar_captcha(usuario, False, concurso)

def check_for_captcha(driver):
    try:
        captcha_element = driver.find_element(By.CSS_SELECTOR, "div.TUXModal.captcha-verify-container")
        if captcha_element.is_displayed():
            return True
    except NoSuchElementException:
        return False
    return False

def retry_find_elements(driver, by, selector, max_attempts=3, wait_time=3):
    """Tenta encontrar elementos com múltiplas tentativas"""
    for attempt in range(max_attempts):
        try:
            elements = WebDriverWait(driver, wait_time).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            if elements:
                return elements
        except (TimeoutException, StaleElementReferenceException) as e:
            if attempt == max_attempts - 1:
                raise e
            time.sleep(2)
    return []

def retry_find_element(driver, by, selector, max_attempts=3, wait_time=3):
    """Tenta encontrar um elemento com múltiplas tentativas"""
    for attempt in range(max_attempts):
        try:
            element = WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except (TimeoutException, StaleElementReferenceException) as e:
            if attempt == max_attempts - 1:
                raise e
            time.sleep(2)
    return None

def check_video_dates(driver, views, days, sadcaptcha, user, concurso):
    log_message(concurso, "INFO", f"Verificando datas dos vídeos para o usuário {user}...")
    try:
        valid_views = 0
        count = 0
        video_elements = retry_find_elements(driver, By.CSS_SELECTOR, "div[data-e2e='user-post-item-list'] div[data-e2e='user-post-item']")
        for i, video_element in enumerate(video_elements):
            if i == 0:
                for _ in range(3):
                    try:
                        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(video_element))
                        driver.execute_script("arguments[0].scrollIntoView(true);", video_element)
                        video_element.click()
                        break
                    except (StaleElementReferenceException, ElementClickInterceptedException):
                        time.sleep(2)
                        video_elements = retry_find_elements(driver, By.CSS_SELECTOR, "div[data-e2e='user-post-item-list'] div[data-e2e='user-post-item']")
                        if video_elements:
                            video_element = video_elements[i]
                time.sleep(2)
            else:
                try:
                    next_button = driver.find_element(By.XPATH, "//*[@id='app']/div[2]/div[4]/div/div[1]/button[3]")
                    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(next_button))
                    driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                    if check_for_captcha(driver):
                        if not solve_captcha(sadcaptcha, driver, user, concurso):
                            log_message(concurso, "ERROR", f"Falha ao resolver CAPTCHA para o usuário {user}.")
                            return 0
                    try:
                        next_button.click()
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        # Tenta simular a tecla seta para baixo se o botão não funcionar
                        webdriver.ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()
                        log_message(concurso, "INFO", f"Usando tecla seta para baixo para o usuário {user}...")
                except NoSuchElementException:
                    # Se não encontrar o botão, usa a tecla seta para baixo
                    webdriver.ActionChains(driver).send_keys(Keys.ARROW_DOWN).perform()
                    log_message(concurso, "INFO", f"Botão não encontrado, usando tecla seta para baixo para o usuário {user}...")
                time.sleep(2)
            try:
                date_text = driver.find_element(By.XPATH, "//span[@data-e2e='browser-nickname']/span[3]").text
                if count < 3:
                    if is_within_days(date_text, days):
                        valid_views += views[i]
                elif is_within_days(date_text, days):
                    valid_views += views[i]
                else:
                    break
                count += 1
            except NoSuchElementException:
                if check_for_captcha(driver):
                    if not solve_captcha(sadcaptcha, driver, user, concurso):
                        log_message(concurso, "ERROR", f"Falha ao resolver CAPTCHA para o usuário {user}.")
                        return 0
            except StaleElementReferenceException:
                date_text = driver.find_element(By.XPATH, "//span[@data-e2e='browser-nickname']/span[3]").text
                if count < 3:
                    if is_within_days(date_text, days):
                        valid_views += views[i]
                elif is_within_days(date_text, days):
                    valid_views += views[i]
                else:
                    break
                count += 1
            try:
                close_button = driver.find_element(By.XPATH, "//*[@id='loginContainer']/div/div/div[3]/div/div[2]")
                WebDriverWait(driver, 10).until(EC.element_to_be_clickable(close_button))
                driver.execute_script("arguments[0].scrollIntoView(true);", close_button)
                if check_for_captcha(driver):
                    if not solve_captcha(sadcaptcha, driver, user, concurso):
                        log_message(concurso, "ERROR", f"Falha ao resolver CAPTCHA para o usuário {user}.")
                        return 0
                try:
                    close_button.click()
                except StaleElementReferenceException:
                    close_button = driver.find_element(By.XPATH, "//*[@id='loginContainer']/div/div/div[3]/div/div[2]")
                    close_button.click()
                time.sleep(2)
            except NoSuchElementException:
                pass
        return valid_views
    except Exception as e:
        log_message(concurso, "ERROR", f"Erro ao verificar datas dos vídeos para o usuário {user}: {e}")
        return 0

def zoom_out(driver):
    driver.execute_script("document.body.style.zoom='50%'")

def scroll_down(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def scrape_user(driver, sadcaptcha, user, days, concurso):
    log_message(concurso, "INFO", f"Iniciando scraping", user)

    def get_views():
        try:
            elements = retry_find_elements(driver, By.CSS_SELECTOR, "div[data-e2e='user-post-item-list'] strong[data-e2e='video-views']")
            if not elements:
                log_message(concurso, "INFO", f"Não há elementos suficientes para o usuário {user}")
                return []
            actions = ActionChains(driver)
            actions.move_to_element(elements[0]).perform()
            time.sleep(0.5)
            elements = retry_find_elements(driver, By.CSS_SELECTOR, "div[data-e2e='user-post-item-list'] strong[data-e2e='video-views']")
            views = [convert_to_int(el.text) for el in elements]
            if all(view == 0 for view in views):
                log_message(concurso, "INFO", f"Todas as visualizações estão em 0 para o usuário {user}. Recarregando a página para verificar novamente.")
                driver.refresh()
                time.sleep(3)
                return scrape_user(driver, sadcaptcha, user, days, concurso)  # Adicionado parâmetro concurso
            return views
        except Exception as e:
            log_message(concurso, "ERROR", f"Erro ao encontrar elementos para o usuário {user}: {e}")
            return []

    url = f"https://www.tiktok.com/@{user}"
    driver.get(url)
    zoom_out(driver)
    scroll_down(driver) 
    
    try:
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='user-post-item-list']"))
        )
    except TimeoutException:
        try:
            private_account_element = driver.find_element(By.CSS_SELECTOR, "p.css-1y4x9xk-PTitle.emuynwa1")
            if "This account is private" in private_account_element.text:
                log_message(concurso, "REMOVED", f"Conta privada", user)
                log_failed_user(concurso, user, "Conta privada")
                with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                    file.write(f"{user} - Conta privada\n")
                return user, 0
            if "No content" in private_account_element.text:
                log_message(concurso, "REMOVED", f"Sem conteúdo", user)
                log_failed_user(concurso, user, "Sem conteúdo")
                with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                    file.write(f"{user} - Sem conteúdo\n")
                return user, 0
            if "Couldn't find this account" in private_account_element.text:
                log_message(concurso, "REMOVED", f"Conta não encontrada", user)
                log_failed_user(concurso, user, "Conta não encontrada")
                with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                    file.write(f"{user} - Conta não encontrada\n")
                return user, 0
            if "Something went wrong" in private_account_element.text:
                try:
                    driver.find_element(By.CSS_SELECTOR, "button.emuynwa3.css-tlik2g-Button-StyledButton.ehk74z00").click()
                    time.sleep(3)
                    return scrape_user(driver, sadcaptcha, user, days, concurso)  # Adicionado parâmetro concurso
                except NoSuchElementException:
                    log_message(concurso, "ERROR", f"Algo deu errado", user)
                    log_failed_user(concurso, user, "Algo deu errado")
                    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                        file.write(f"{user} - Algo deu errado\n")
                    return user, 0
        except NoSuchElementException:
            log_message(concurso, "ERROR", f"Elemento não encontrado", user)
            log_failed_user(concurso, user, "Elemento não encontrado")
            if not solve_captcha(sadcaptcha, driver, user, concurso):
                with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                    file.write(f"{user} - Falha ao resolver CAPTCHA\n")
                return user, 0

    try:
        driver.find_element(By.XPATH, "//*[@id='loginContainer']/div/div/div[3]/div/div[2]").click()
        time.sleep(2)
    except NoSuchElementException:
        pass

    views = get_views()
    if not views:
        user = user + user[-1]
        driver.get(f"https://www.tiktok.com/@{user}")
        zoom_out(driver)
        scroll_down(driver)
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[data-e2e='user-post-item-list']"))
            )
        except TimeoutException:
            try:
                private_account_element = driver.find_element(By.CSS_SELECTOR, "p.css-1y4x9xk-PTitle.emuynwa1")
                if "This account is private" in private_account_element.text:
                    log_message(concurso, "REMOVED", f"Conta privada", user)
                    log_failed_user(concurso, user, "Conta privada")
                    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                        file.write(f"{user} - Conta privada\n")
                    return user, 0
                if "No content" in private_account_element.text:
                    log_message(concurso, "REMOVED", f"Sem conteúdo", user)
                    log_failed_user(concurso, user, "Sem conteúdo")
                    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                        file.write(f"{user} - Sem conteúdo\n")
                    return user, 0
                if "Couldn't find this account" in private_account_element.text:
                    log_message(concurso, "REMOVED", f"Conta não encontrada", user)
                    log_failed_user(concurso, user, "Conta não encontrada")
                    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                        file.write(f"{user} - Conta não encontrada\n")
                    return user, 0
                if "Something went wrong" in private_account_element.text:
                    try:
                        driver.find_element(By.CSS_SELECTOR, "button.emuynwa3.css-tlik2g-Button-StyledButton.ehk74z00").click()
                        time.sleep(3)
                        return scrape_user(driver, sadcaptcha, user, days, concurso)  # Adicionado parâmetro concurso
                    except NoSuchElementException:
                        log_message(concurso, "ERROR", f"Algo deu errado", user)
                        log_failed_user(concurso, user, "Algo deu errado")
                        with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                            file.write(f"{user} - Algo deu errado\n")
                        return user, 0
            except NoSuchElementException:
                log_message(concurso, "ERROR", f"Elemento não encontrado", user)
                log_failed_user(concurso, user, "Elemento não encontrado")
                if not solve_captcha(sadcaptcha, driver, user, concurso):
                    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
                        file.write(f"{user} - Falha ao resolver CAPTCHA\n")
                    return user, 0
        views = get_views()

    valid_views = check_video_dates(driver, views, days, sadcaptcha, user, concurso)
    with open(f"database/{concurso}/results/TikTokResults.txt", "a", encoding="utf-8") as file:
        file.write(f"{user} - TikTok: {valid_views}\n")
    log_message(concurso, "INFO", f"Scraping concluído para o usuário: {user} com {valid_views} visualizações válidas.")
    return user, valid_views if valid_views is not None else 0

def perguntar_gerar_resultado():
    if input("Deseja gerar o resultado executando o arquivo ranking.py? (s/n): ").lower() == 's':
        subprocess.run(["python", "ranking.py"])

def scrape_users(driver, sadcaptcha, users, days, result_file, concurso):
    # Primeiro, lê os resultados existentes com lock
    existing_results = {}
    with file_lock:
        try:
            with open(result_file, "r", encoding="utf-8") as file:
                for line in file:
                    if " - TikTok: " in line:
                        user, views = line.split(" - TikTok: ")
                        existing_results[user.strip()] = int(views.strip())
        except FileNotFoundError:
            pass

    # Processa os novos usuários e acumula resultados
    new_results = {}
    for user in users:
        if user not in existing_results:  # Só processa se não existir resultado
            result = scrape_user(driver, sadcaptcha, user, days, concurso)
            if result:
                new_results[result[0]] = result[1]

    # Atualiza os resultados existentes com os novos
    with file_lock:
        # Lê novamente para garantir dados atualizados
        try:
            with open(result_file, "r", encoding="utf-8") as file:
                for line in file:
                    if " - TikTok: " in line:
                        user, views = line.split(" - TikTok: ")
                        existing_results[user.strip()] = int(views.strip())
        except FileNotFoundError:
            pass

        # Adiciona os novos resultados
        existing_results.update(new_results)

        # Ordena e salva todos os resultados
        results = [(user, views) for user, views in existing_results.items()]
        results.sort(key=lambda x: x[1], reverse=True)

        with open(result_file, "w", encoding="utf-8") as file:
            for user, views in results:
                file.write(f"{user} - TikTok: {views}\n")

def run_scrape(driver, sadcaptcha, users, days, result_file, concurso):
    scrape_users(driver, sadcaptcha, users, days, result_file, concurso)

def verificar_usuarios_com_zero_views(driver, sadcaptcha, days, result_file, concurso):
    with file_lock:
        with open(result_file, "r", encoding="utf-8") as file:
            lines = file.readlines()
        
        zero_view_users = [line.split(" - TikTok: ")[0] for line in lines if " - TikTok: 0" in line]
    
    if zero_view_users:
        log_message(concurso, "INFO", f"Verificando novamente {len(zero_view_users)} usuários com 0 visualizações.")
        updated_results = {}
        for user in zero_view_users:
            result = scrape_user(driver, sadcaptcha, user, days, concurso)
            if result:
                updated_results[result[0]] = result[1]

        with file_lock:
            with open(result_file, "r", encoding="utf-8") as file:
                lines = file.readlines()
            
            current_results = {}
            for line in lines:
                if " - TikTok: " in line:
                    user, views = line.split(" - TikTok: ")
                    current_results[user.strip()] = int(views.strip())
            
            current_results.update(updated_results)
            
            results = [(user, views) for user, views in current_results.items()]
            results.sort(key=lambda x: x[1], reverse=True)
            
            with open(result_file, "w", encoding="utf-8") as file:
                for user, views in results:
                    file.write(f"{user} - TikTok: {views}\n")

def parse_date_input(date_str):
    """
    Processa a entrada de data em diferentes formatos:
    - Número de dias (ex: "28")
    - Data completa (ex: "08-09-2024" ou "08/09/2024")
    - Data curta (ex: "08-09" ou "08/09")
    """
    today = datetime.now()
    
    # Tenta interpretar como número de dias
    try:
        days = int(date_str)
        target_date = today - timedelta(days=days)
        return target_date, days
    except ValueError:
        pass
    
    # Padroniza o separador para '-'
    date_str = date_str.replace('/', '-')
    
    # Tenta interpretar como data completa ou curta
    date_patterns = [
        ('%d-%m-%Y', True),  # Data completa
        ('%d-%m', False)     # Data curta
    ]
    
    for pattern, is_full in date_patterns:
        try:
            if not is_full:
                # Adiciona o ano atual para datas curtas
                date_str = f"{date_str}-{today.year}"
            target_date = datetime.strptime(date_str, '%d-%m-%Y')
            
            # Ajusta para o ano anterior se a data for futura
            if target_date > today:
                target_date = target_date.replace(year=target_date.year - 1)
                
            days = (today - target_date).days
            return target_date, days
        except ValueError:
            continue
    
    raise ValueError("Formato de data inválido. Use dias (ex: 28) ou data (ex: 08-09-2024, 08-09)")

def format_date_range(target_date):
    today = datetime.now()
    days = (today - target_date).days
    
    def format_date(date):
        return date.strftime('%d/%m/%Y')
    
    range_str = (
        f"🔍 Período de busca:\n"
        f"• De: {format_date(target_date)}\n"
        f"• Até: {format_date(today)}\n"
        f"• Total: {days} dia{'s' if days != 1 else ''}"
    )
    
    return range_str

def verificar_ou_criar_pastas(concurso):
    base_path = f"database/{concurso}"
    subdirs = ["logs/instagram", "logs/facebook", "logs/tiktok", "logs/youtube", "results", "users"]
    user_files = ["usersFace.txt", "usersIg.txt", "usersTtk.txt", "usersYt.txt"]

    for subdir in subdirs:
        path = os.path.join(base_path, subdir)
        os.makedirs(path, exist_ok=True)

    for user_file in user_files:
        path = os.path.join(base_path, "users", user_file)
        if not os.path.exists(path):
            with open(path, "w") as f:
                pass

def fechar_driver_seguro(driver):
    try:
        # Tenta fechar todas as janelas primeiro
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                driver.close()
            except:
                pass
        
        # Então tenta encerrar o driver
        try:
            driver.quit()
        except:
            pass
    except:
        pass

def main():
    start_time = time.time()
    service = Service()

    concurso = input("Digite o nome do concurso: ")
    verificar_ou_criar_pastas(concurso)

    num_instances = int(input("Digite o número de instâncias do Chrome para iniciar: "))  

    drivers = []
    sadcaptchas = []
    api_key = "ace45faba83e996d44def895647ae123"

    try:
        for _ in range(num_instances):
            options = uc.ChromeOptions()
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.media_stream": 2,
                "profile.default_content_setting_values.media_stream_mic": 2,
                "profile.default_content_setting_values.media_stream_camera": 2,
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.auto_play": 2
            }
            options.add_experimental_option("prefs", prefs)
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")

            # Configuração do Chrome usando webdriver-manager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            drivers.append(driver)
            sadcaptchas.append(SeleniumSolver(driver, api_key))

        with open(f"database/{concurso}/users/usersTtk.txt", "r") as file:
            users = [line.strip() for line in file.readlines()]

        while True:
            try:
                date_input = input("Digite o período de busca (dias ou data): ")
                target_date, days = parse_date_input(date_input)
                print("\n" + format_date_range(target_date) + "\n")
                confirm = input("Confirmar período? (s/n): ").lower()
                if confirm == 's':
                    break
            except ValueError as e:
                print(f"Erro: {e}")

        user_chunks = [users[i::num_instances] for i in range(num_instances)] 

        result_file = f"database/{concurso}/results/TikTokResults.txt"
        with open(result_file, "w", encoding="utf-8") as file:
            file.write("")

        threads = []
        for i in range(num_instances):
            thread = threading.Thread(target=run_scrape, args=(drivers[i], sadcaptchas[i], user_chunks[i], days, result_file, concurso))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verifica usuários com zero views antes de fechar os drivers
        for i in range(num_instances):
            try:
                verificar_usuarios_com_zero_views(drivers[i], sadcaptchas[i], days, result_file, concurso)
            except Exception as e:
                log_message(concurso, f"Erro ao verificar usuários com zero views na instância {i}: {e}")

    finally:
        # Fecha os drivers de forma segura
        log_message(concurso, "INFO", "Fechando as instâncias do Chrome...")
        for driver in drivers:
            fechar_driver_seguro(driver)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        log_message(concurso, "INFO", f"Tempo total de execução: {elapsed_time:.2f} segundos")
        perguntar_gerar_resultado()
        input("Pressione Enter para fechar o programa...")

if __name__ == "__main__":
    main()