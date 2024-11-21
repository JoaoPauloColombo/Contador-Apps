import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from datetime import datetime, timedelta
import threading
import json
import random
from requests.exceptions import ConnectionError
from selenium.webdriver.common.keys import Keys
import itertools
import sys
import os
import re
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

def human_like_delay(min_delay=1, max_delay=3):
    time.sleep(random.uniform(min_delay, max_delay))

def load_cookies(driver, cookies_file):
    with open(cookies_file, "r") as file:
        cookies = json.load(file)
        for cookie in cookies:
            driver.execute_script(
                "document.cookie = arguments[0] + '=' + arguments[1] + '; domain=' + arguments[2] + '; path=' + arguments[3] + '; secure=' + arguments[4] + ';';",
                cookie['name'], cookie['value'], cookie['domain'], cookie['path'], 'true' if cookie['secure'] else 'false'
            )

def login_with_cookies(driver, cookies_file):
    driver.get("https://www.instagram.com/")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        load_cookies(driver, cookies_file)
        driver.refresh()
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._ac7v"))
            )
        except TimeoutException:
            pass
    except TimeoutException:
        pass
    except NoSuchElementException as e:
        pass
    except Exception as e:
        pass

def scroll_down(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_like_delay(2, 4)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def scroll_up(driver):
    driver.execute_script("window.scrollTo(0, 0);")
    human_like_delay(2, 4)

def is_within_days(date_str, days, concurso):
    now = datetime.now()
    target_date = now - timedelta(days=days)
    
    try:
        if 'h' in date_str:
            hours = int(date_str.split('h')[0])
            video_date = now - timedelta(hours=hours)
        elif 'm' in date_str:
            minutes = int(date_str.split('m')[0])
            video_date = now - timedelta(minutes=minutes)
        elif 'd' in date_str:
            days_ago = int(date_str.split('d')[0])
            video_date = now - timedelta(days=days_ago)
        elif 'w' in date_str:
            weeks_ago = int(date_str.split('w')[0])
            video_date = now - timedelta(weeks=weeks_ago)
        else:
            video_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        
        # Ajuste para considerar apenas as datas (sem hora)
        video_date = video_date.date()
        target_date = target_date.date()
        
        # Log para depuração
        log_step(f"Comparando datas - Vídeo: {video_date}, Alvo: {target_date}", concurso)
        
        # Verifica se a data do vídeo é maior ou igual à data limite
        is_valid = video_date >= target_date
        log_step(f"Vídeo {'está' if is_valid else 'não está'} dentro do período", concurso)
        
        return is_valid
        
    except ValueError as e:
        log_step(f"Erro ao verificar a data: {str(e)}", concurso, error=e)
        return False

def get_views(driver, concurso):
    views = []
    try:
        views_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div._ac7v div._aajy span.html-span.xdj266r.x11i5rnm.xat24cr.x1mh8g0r.xexx8yu.x4uap5.x18d9i69.xkhd6sd.x1hl2dhg.x16tdsg8.x1vvkbs"))
        )
        for view in views_elements:
            try:
                view_text = view.text.replace(',', '')
                if 'K' in view_text:
                    views.append(int(float(view_text.replace('K', '')) * 1000))
                elif 'M' in view_text:
                    views.append(int(float(view_text.replace('M', '')) * 1000000))
                else:
                    views.append(int(view_text))
            except ValueError:
                views.append(0)
    except Exception as e:
        log_step(f"Erro ao coletar visualizações: {e}", concurso)
    log_step(f"Visualizações coletadas: {views}", concurso)  # Log temporário
    return views

def format_date(date_str):
    now = datetime.now()
    try:
        if 'h' in date_str:
            hours = int(date_str.split('h')[0])
            return f"{hours} hora{'s' if hours != 1 else ''} atrás"
        elif 'm' in date_str:
            minutes = int(date_str.split('m')[0])
            return f"{minutes} minuto{'s' if minutes != 1 else ''} atrás"
        elif 'd' in date_str:
            days_ago = int(date_str.split('d')[0])
            return f"{days_ago} dia{'s' if days_ago != 1 else ''} atrás"
        elif 'w' in date_str:
            weeks_ago = int(date_str.split('w')[0])
            return f"{weeks_ago} semana{'s' if weeks_ago != 1 else ''} atrás"
        else:
            video_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%fZ')
            return video_date.strftime('%d de %B de %Y')
    except Exception as e:
        print(f"Erro ao formatar data: {e}")
        return date_str

def ask_for_xpath():
    return input("Por favor, insira o XPath da data do vídeo: ")

def log_step(message, concurso, user="", error=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_path = f"database/{concurso}/logs/instagram/scraping_steps.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as file:
        log_message = f"[{timestamp}] {message}"
        if user:
            log_message = f"[{timestamp}] [{user}] {message}"
        if error:
            log_message += f"\nError: {str(error)}"
        file.write(log_message + "\n")

def get_views_from_element(element, concurso):
    """Extrai o número de visualizações de um elemento de vídeo"""
    try:
        view_span = element.find_element(By.CSS_SELECTOR, "div._aajy span.html-span.xdj266r")
        view_text = view_span.text.replace(',', '')
        if 'K' in view_text:
            return int(float(view_text.replace('K', '')) * 1000)
        elif 'M' in view_text:
            return int(float(view_text.replace('M', '')) * 1000000)
        return int(view_text)
    except Exception as e:
        log_step(f"Erro ao extrair visualizações: {str(e)}", concurso, error=e)
        return None

def find_video_by_views(driver, target_views, concurso):
    """Encontra um vídeo específico pelo número de visualizações"""
    try:
        # Procura por todos os containers de vídeo
        video_containers = driver.find_elements(By.CSS_SELECTOR, "div._ac7v > div")
        log_step(f"Procurando vídeo com {target_views} visualizações", concurso)
        
        for container in video_containers:
            try:
                # Encontra o link do reel e as visualizações no container
                video_link = container.find_element(By.CSS_SELECTOR, "a[href*='/reel/']")
                views_div = container.find_element(By.CSS_SELECTOR, "div._aajy")
                current_views = get_views_from_element(views_div, concurso)
                
                if current_views == target_views:
                    log_step(f"Vídeo encontrado com {current_views} visualizações", concurso)
                    return video_link
                
            except Exception as e:
                continue
                
        log_step(f"Nenhum vídeo encontrado com {target_views} visualizações", concurso)
        return None
    except Exception as e:
        log_step(f"Erro ao procurar vídeo: {str(e)}", concurso, error=e)
        return None

def click_first_video_and_collect_views(driver, days, views, concurso):
    total_views = 0
    validated_views = []
    processed_dates = set()
    remaining_views = views.copy()  # Cria uma cópia da lista de visualizações
    videos_processed = 0

    date_selectors = [
        (By.CSS_SELECTOR, "time._a9ze._a9zf"),
        (By.CSS_SELECTOR, "time.x1p4m5qa"),
        (By.XPATH, "//div[@role='dialog']//time"),
        (By.CSS_SELECTOR, "time[datetime]"),
        (By.CSS_SELECTOR, "time"),
    ]

    log_step(f"Iniciando com {len(remaining_views)} visualizações para verificar", concurso)
    
    try:
        while remaining_views:
            target_views = remaining_views[0]  # Próxima visualização a ser verificada
            log_step(f"Procurando vídeo com {target_views} visualizações", concurso)
            
            # Procura o vídeo específico
            video_link = find_video_by_views(driver, target_views, concurso)
            
            if not video_link:
                log_step(f"Vídeo com {target_views} visualizações não encontrado, tentando scroll", concurso)
                # Faz scroll e tenta novamente
                viewport_height = driver.execute_script("return window.innerHeight")
                current_scroll = driver.execute_script("return window.pageYOffset")
                driver.execute_script(f"window.scrollTo({current_scroll}, {current_scroll + viewport_height/2});")
                human_like_delay(2, 3)
                video_link = find_video_by_views(driver, target_views, concurso)
                
                if not video_link:
                    log_step(f"Vídeo não encontrado mesmo após scroll, removendo da lista", concurso)
                    remaining_views.pop(0)
                    continue

            try:
                log_step("Tentando clicar no vídeo", concurso)
                driver.execute_script("arguments[0].click();", video_link)
                human_like_delay(2, 4)

                # Aguarda e verifica o diálogo do reel
                try:
                    dialog = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='dialog']"))
                    )
                    
                    # Procura o elemento de data
                    date_element = None
                    for selector_type, selector in date_selectors:
                        try:
                            date_element = WebDriverWait(driver, 2).until(
                                EC.presence_of_element_located((selector_type, selector))
                            )
                            if date_element:
                                break
                        except:
                            continue
                    
                    if not date_element:
                        log_step("Data não encontrada, pulando vídeo", concurso)
                        remaining_views.pop(0)
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        continue

                    date_text = date_element.get_attribute("datetime") or \
                              date_element.get_attribute("title") or \
                              date_element.text

                    if not date_text:
                        log_step("Texto da data não encontrado, pulando vídeo", concurso)
                        remaining_views.pop(0)
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        continue

                    formatted_date = format_date(date_text)
                    log_step(f"Data encontrada: {formatted_date}", concurso)

                    if is_within_days(date_text, days, concurso):
                        current_views = remaining_views.pop(0)  # Remove e obtém a visualização atual
                        total_views += current_views
                        validated_views.append((current_views, formatted_date))
                        videos_processed += 1
                        log_step(f"Vídeo processado: {current_views} visualizações. Restam {len(remaining_views)}", concurso)
                    else:
                        log_step("Vídeo fora do período, encerrando verificação", concurso)
                        break

                except TimeoutException:
                    log_step("Timeout ao esperar diálogo do reel", concurso)
                    remaining_views.pop(0)
                    continue
                
                finally:
                    try:
                        webdriver.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        human_like_delay(1, 2)
                    except:
                        pass

            except Exception as e:
                log_step(f"Erro ao processar vídeo: {str(e)}", concurso, error=e)
                remaining_views.pop(0)
                continue

    except Exception as e:
        log_step(f"Erro geral: {str(e)}", concurso, error=e)

    log_step(f"Finalizado com {len(validated_views)} vídeos validados de {len(views)} originais", concurso)
    return validated_views

def scroll_and_collect_views_during_scroll(driver, concurso):
    views = []
    processed_views = set()  # Conjunto para controlar visualizações já coletadas
    last_height = driver.execute_script("return document.body.scrollHeight")

    while True:
        # Coleta as visualizações na posição atual da página
        new_views = get_views(driver, concurso)
        
        # Adiciona apenas visualizações não processadas anteriormente
        for view in new_views:
            if view not in processed_views:
                views.append(view)
                processed_views.add(view)

        # Rola para baixo na página
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        human_like_delay(2, 4)

        # Verifica se chegou ao fim da página
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    # Removemos o reversed aqui, pois queremos manter a ordem original
    return views  # Agora retorna as views na ordem correta (mais recente primeiro)

def log_failed_user(concurso, user, reason):
    log_path = f"database/{concurso}/logs/instagram/failed_users.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as file:
        file.write(f"{user}: {reason}\n")

def log_message(concurso, level, message, user="", error=None):
    os.makedirs(f"database/{concurso}/logs/instagram", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] "
    if user:
        log_entry += f"[{user}] "
    log_entry += message
    if error:
        log_entry += f"\nError: {str(error)}"

    log_files = {
        "ALERT": f"database/{concurso}/logs/instagram/alerts.log",
        "ERROR": f"database/{concurso}/logs/instagram/errors.log",
        "INFO": f"database/{concurso}/logs/instagram/info.log",
        "REMOVED": f"database/{concurso}/logs/instagram/removedAccounts.log"
    }

    log_file = log_files.get(level, f"database/{concurso}/logs/instagram/general.log")
    
    with open(log_file, "a", encoding="utf-8") as file:
        file.write(log_entry + "\n")

def remove_user_from_files(concurso, user):
    try:
        with open(f"database/{concurso}/users/usersIg.txt", "r", encoding="utf-8") as file:
            users = file.readlines()
        with open(f"database/{concurso}/users/usersIg.txt", "w", encoding="utf-8") as file:
            file.writelines([line for line in users if user not in line])
    except Exception as e:
        log_message(concurso, "ERROR", f"Erro ao remover usuário do arquivo de usuários", user, e)

    try:
        with open(f"database/{concurso}/results/ReelsResults.txt", "r", encoding="utf-8") as file:
            results = file.readlines()
        with open(f"database/{concurso}/results/ReelsResults.txt", "w", encoding="utf-8") as file:
            file.writelines([line for line in results if user not in line])
    except Exception as e:
        log_message(concurso, "ERROR", f"Erro ao remover usuário do arquivo de resultados", user, e)

def check_page_exists(driver):
    try:
        error_message = driver.find_element(By.CSS_SELECTOR, "span[dir='auto']")
        if "Sorry, this page isn't available" in error_message.text:
            return False
        return True
    except NoSuchElementException:
        return True

def scrape_user(driver, user, days, concurso):
    try:
        user = user.split(" - Reels")[0]
        driver.get(f"https://www.instagram.com/{user}/reels/")

        if not check_page_exists(driver):
            log_message(concurso, "REMOVED", f"Conta não existe ou foi removida", user)
            remove_user_from_files(concurso, user)
            return user, 0, []

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div._ac7v"))
            )
        except TimeoutException:
            log_failed_user(concurso, user, "Timeout ao carregar página")
            with open(f"database/{concurso}/results/ReelsResults.txt", "a", encoding="utf-8") as file:
                file.write(f"{user} - Reels: 0\n")
            return user, 0, []

        all_views = scroll_and_collect_views_during_scroll(driver, concurso)

        if not all_views:
            log_failed_user(concurso, user, "Nenhuma visualização encontrada")

        scroll_up(driver)

        validated_views = click_first_video_and_collect_views(driver, days, all_views, concurso)

        total_validated_views = sum(view[0] for view in validated_views)

        if total_validated_views == 0:
            log_failed_user(concurso, user, "Zero visualizações")

        with open(f"database/{concurso}/results/ReelsResults.txt", "a", encoding="utf-8") as file:
            file.write(f"{user} - Reels: {total_validated_views}\n")

        return user, total_validated_views, validated_views
    except ConnectionError as e:
        log_failed_user(concurso, user, f"Erro de conexão: {str(e)}")
        with open(f"database/{concurso}/results/ReelsResults.txt", "a", encoding="utf-8") as file:
            file.write(f"{user} - Reels: 0\n")
        return user, 0, []
    except Exception as e:
        log_failed_user(concurso, user, f"Erro geral: {str(e)}")
        with open(f"database/{concurso}/results/ReelsResults.txt", "a", encoding="utf-8") as file:
            file.write(f"{user} - Reels: 0\n")
        return user, 0, []

def run_scrape(driver, users, days, concurso):
    for user in users:
        try:
            scrape_user(driver, user, days, concurso)
        except Exception as e:
            log_step(f"Erro ao processar usuário {user}: {str(e)}", concurso, error=e)

def recheck_zero_views(drivers, days, concurso):
    try:
        with open(f"database/{concurso}/results/ReelsResults.txt", "r", encoding="utf-8") as file:
            lines = file.readlines()
    except FileNotFoundError:
        return

    existing_results = {}
    for line in reversed(lines):
        user = line.split(" - Reels")[0].strip()
        views = line.split(":")[1].strip()
        if user not in existing_results:
            existing_results[user] = views

    zero_view_users = [user for user, views in existing_results.items() if views == "0"]
    
    if not zero_view_users:
        return

    num_instances = len(drivers)
    user_chunks = [zero_view_users[i::num_instances] for i in range(num_instances)]

    threads = []
    results = {}

    def recheck_user_chunk(driver, users_chunk, days, concurso):
        for user in users_chunk:
            try:
                user, views, validated_views = scrape_user(driver, user, days, concurso)
                results[user] = (views, validated_views)
            except Exception as e:
                pass

    for i in range(num_instances):
        thread = threading.Thread(target=recheck_user_chunk, args=(drivers[i], user_chunks[i], days, concurso))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    for user, (views, _) in results.items():
        existing_results[user] = str(views)

    with open(f"database/{concurso}/results/ReelsResults.txt", "w", encoding="utf-8") as file:
        for user, views in existing_results.items():
            file.write(f"{user} - Reels: {views}\n")

def parse_date_input(date_str):
    today = datetime.now()
    
    try:
        days = int(date_str)
        target_date = today - timedelta(days=days)
        return target_date, days
    except ValueError:
        pass
    
    date_str = date_str.replace('/', '-')
    
    date_patterns = [
        ('%d-%m-%Y', True), 
        ('%d-%m', False)
    ]
    
    for pattern, is_full in date_patterns:
        try:
            if not is_full:
                date_str = f"{date_str}-{today.year}"
            target_date = datetime.strptime(date_str, '%d-%m-%Y')
            
            if target_date > today:
                target_date = target_date.replace(year=target_date.year - 1)
                
            days = (today - target_date).days
            return target_date, days
        except ValueError:
            continue
    
    raise ValueError("Formato de data inválido. Use dias (ex: 28) ou data (ex: 08-09-2024, 08-09)")

def format_date_range(target_date):
    """Formata o período de busca de forma amigável"""
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

def main():
    start_time = time.time()
    service = Service()

    concurso = input("Digite o nome do concurso: ")
    verificar_ou_criar_pastas(concurso)

    num_instances = int(input("Digite o número de instâncias do Chrome para iniciar: ")) 

    drivers = []
    
    with open(f"database/{concurso}/users/usersIg.txt", "r", encoding="utf-8") as file:
        users = [line.strip() for line in file.readlines()]
        user_chunks = [users[i::num_instances] for i in range(num_instances)] 

    for i in range(num_instances):
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
        options.add_argument("--window-size=1920,1080")
        
        # Configuração do Chrome usando webdriver-manager
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        drivers.append(driver)

    login_with_cookies(drivers[0], f"database/cookies/cookieInstagram.json")

    acao_inicial = input("Deseja iniciar um novo check ou verificar os usuários com 0 visualizações? (novo/verificar): ").lower()

    log_files = [
        f"database/{concurso}/logs/instagram/alerts.log",
        f"database/{concurso}/logs/instagram/errors.log",
        f"database/{concurso}/logs/instagram/info.log",
        f"database/{concurso}/logs/instagram/removedAccounts.log",
        f"database/{concurso}/logs/instagram/general.log"
    ]
    
    for log_file in log_files:
        with open(log_file, "w", encoding="utf-8") as file:
            file.write("")

    if acao_inicial == "verificar":
        with open(f"database/{concurso}/logs/instagram/failed_users.log", "w", encoding="utf-8") as file:
            file.write("")
        
        date_input = None
        while not date_input:
            try:
                date_input = input("Digite o período de busca (dias ou data): ")
                target_date, days = parse_date_input(date_input)
                print("\n" + format_date_range(target_date) + "\n")
                if input("Confirmar período? (s/n): ").lower() != 's':
                    date_input = None
            except ValueError as e:
                print(f"Erro: {e}")
                date_input = None

        def animate():
            start_time = time.time()
            while not done:
                elapsed_time = time.time() - start_time
                minutes, seconds = divmod(int(elapsed_time), 60)
                time_str = f"{minutes:02}:{seconds:02}"
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"╔════════════════════════════╗")
                print(f"║ Tempo: {time_str}              ║")
                print(f"╚════════════════════════════╝")
                time.sleep(1)
            print("\rConcluído!")

        done = False
        t = threading.Thread(target=animate)
        t.start()
        
        try:
            recheck_zero_views(drivers, days, concurso)
        finally:
            done = True
            t.join()
            
    else:
        with open(f"database/{concurso}/results/ReelsResults.txt", "w", encoding="utf-8") as file:
            file.write("")
        with open(f"database/{concurso}/logs/instagram/failed_users.log", "w", encoding="utf-8") as file:
            file.write("")
        
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
              
        print("Iniciando processamento com estimativa de tempo...")
        sample_users = users[:10]
        remaining_users = users[10:] 
          
        sample_start = time.time()
        for user in sample_users:
            scrape_user(drivers[0], user, days, concurso)
        sample_time = time.time() - sample_start
        
        estimated_time_per_user = sample_time / 10
        total_estimated_time = estimated_time_per_user * len(remaining_users)
        
        def animate():
            anim_start = time.time()
            while not done:
                current_time = time.time() - anim_start
                est_remaining = total_estimated_time - current_time
                
                if est_remaining < 0:
                    est_remaining = 0
                    
                cur_minutes, cur_seconds = divmod(int(current_time), 60)
                est_minutes, est_seconds = divmod(int(est_remaining), 60)
                
                current_str = f"{cur_minutes:02}:{cur_seconds:02}"
                estimated_str = f"{est_minutes:02}:{est_seconds:02}"
                
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"╔════════════════════════════╗")
                print(f"║ Tempo: {current_str}              ║")
                print(f"║ Restante: {estimated_str}         ║")
                print(f"╚════════════════════════════╝")
                time.sleep(1)
            print("\rConcluído!")

        done = False
        t = threading.Thread(target=animate)
        t.start()

        try:
            remaining_chunks = [remaining_users[i::num_instances] for i in range(num_instances)]
            
            threads = []
            for i in range(num_instances):
                thread = threading.Thread(target=run_scrape, args=(drivers[i], remaining_chunks[i], days, concurso))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            recheck_zero_views(drivers, days, concurso)
        finally:
            done = True
            t.join()

    for driver in drivers:
        driver.quit()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nTempo total de execução: {elapsed_time:.2f} segundos")  

    input("\nPressione Enter para fechar o programa...")

if __name__ == "__main__":
    main() 

