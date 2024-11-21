import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import subprocess
from datetime import datetime, timedelta
import threading
import os
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

file_lock = threading.Lock()

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

def get_video_date(driver):
    try:
        date_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.YtwFactoidRendererFactoid[role='text'][aria-label*='ago'], div.YtwFactoidRendererFactoid[role='text'][aria-label*='202']"))
        )
        date_text = date_element.get_attribute("aria-label")
        return date_text
    except TimeoutException:
        return None
    except NoSuchElementException:
        return None
    except Exception:
        return None
    
def is_within_days(date_text, days):
    try:
        current_date = datetime.now()
        if 'minute' in date_text:
            minutes_ago = int(date_text.split(' ')[0])
            video_date = current_date - timedelta(minutes=minutes_ago)
        elif 'hour' in date_text:
            hours_ago = int(date_text.split(' ')[0])
            video_date = current_date - timedelta(hours=hours_ago)
        elif 'day' in date_text:
            days_ago = int(date_text.split(' ')[0])
            video_date = current_date - timedelta(days=days_ago)
        elif 'week' in date_text:
            weeks_ago = int(date_text.split(' ')[0])
            video_date = current_date - timedelta(weeks=weeks_ago)
        else:
            video_date = datetime.strptime(date_text, "%b %d, %Y")
        delta = current_date - video_date
        return delta.days <= days
    except ValueError:
        return False

def is_ad_video(driver):
    try:
        ad_element = driver.find_element(By.CSS_SELECTOR, "div.badge-shape-wiz__text")
        if "Sponsored" in ad_element.text:
            return True
        return False
    except NoSuchElementException:
        return False

def zoom_out(driver):
    driver.execute_script("document.body.style.zoom='25%'")

def scroll_down(driver):
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_views(driver, days):
    total_views = 0
    videos_considerados = 0
    video_index = 1

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#contents"))
        )

        zoom_out(driver)
        scroll_down(driver)

        video_elements = driver.find_elements(By.CSS_SELECTOR, "div#contents ytm-shorts-lockup-view-model a")
        views_elements = driver.find_elements(By.CSS_SELECTOR, "div.ShortsLockupViewModelHostMetadataSubhead span.yt-core-attributed-string[role='text']")
        title_elements = driver.find_elements(By.CSS_SELECTOR, "div#contents ytm-shorts-lockup-view-model h3")

        if len(video_elements) // 2 != len(views_elements) or len(video_elements) // 2 != len(title_elements):
            return total_views

        for video_index in range(1, len(video_elements), 2):
            try:
                views_text = views_elements[video_index // 2].text.replace(' views', '').replace(' view', '')
                
                if 'M' in views_text:
                    number = float(views_text.replace('M', ''))
                    views = int(number * 1000000)
                elif 'K' in views_text:
                    number = float(views_text.replace('K', ''))
                    views = int(number * 1000)
                elif 'No views' in views_text or 'No' in views_text:
                    views = 0
                else:
                    views = int(views_text.replace(',', ''))

                video_element = video_elements[video_index]
                video_element.click()
                time.sleep(2)

                if is_ad_video(driver):
                    driver.back()
                    time.sleep(2)
                    continue

                video_date_text = get_video_date(driver)
                
                if not video_date_text:
                    driver.back()
                    time.sleep(2)
                    continue

                if not is_within_days(video_date_text, days):
                    if videos_considerados >= 3:
                        break
                    else:
                        driver.back()
                        time.sleep(2)
                        continue

                total_views += views
                videos_considerados += 1

                driver.back()
                time.sleep(2)

            except Exception:
                break

    except Exception:
        pass

    return total_views

def scrape_user(driver, user, days, concurso):
    print(f"Iniciando scraping do canal: @{user}")

    url = f"https://www.youtube.com/@{user}/shorts"
    driver.get(url)

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div#contents"))
        )
    except TimeoutException:
        with file_lock:
            with open(f"database/{concurso}/results/ShortsResults.txt", "a", encoding="utf-8") as file:
                file.write(f"{user} - Canal não encontrado\n")
        return user, 0

    total_views = get_views(driver, days)

    with file_lock:
        with open(f"database/{concurso}/results/ShortsResults.txt", "a", encoding="utf-8") as file:
            file.write(f"{user} - Shorts: {total_views}\n")

    return user, total_views

def scrape_users(driver, users, days, result_file, concurso):
    existing_results = {}
    with file_lock:
        try:
            with open(result_file, "r", encoding="utf-8") as file:
                for line in file:
                    if " - Shorts: " in line:
                        user, views = line.split(" - Shorts: ")
                        existing_results[user.strip()] = int(views.strip())
        except FileNotFoundError:
            pass

    new_results = {}
    for user in users:
        result = scrape_user(driver, user, days, concurso)
        if result:
            new_results[result[0]] = result[1]

    with file_lock:
        try:
            with open(result_file, "r", encoding="utf-8") as file:
                for line in file:
                    if " - Shorts: " in line:
                        user, views = line.split(" - Shorts: ")
                        existing_results[user.strip()] = int(views.strip())
        except FileNotFoundError:
            pass

        existing_results.update(new_results)

        results = [(user, views) for user, views in existing_results.items()]
        results.sort(key=lambda x: x[1], reverse=True)

        with open(result_file, "w", encoding="utf-8") as file:
            for user, views in results:
                file.write(f"{user} - Shorts: {views}\n")

def verificar_usuarios_com_zero_views(driver, users, days, result_file, concurso):
    for user in users:
        try:
            scrape_user(driver, user, days, concurso)
        except Exception as e:
            print(f"Erro ao processar o canal {user}: {e}")

def perguntar_gerar_resultado():
    resposta = input("Deseja gerar o resultado executando o arquivo ranking.py? (s/n): ")
    if resposta.lower() == 's':
        subprocess.run(["python", "ranking.py"])

def recheck_zero_views(drivers, days, concurso):
    if not isinstance(drivers, list):
        drivers = [drivers]

    with open(f"database/{concurso}/results/ShortsResults.txt", "r") as file:
        lines = file.readlines()

    zero_view_users = [line.split(" - ")[0] for line in lines if " - Shorts: 0" in line]

    if not zero_view_users:
        print("Nenhum usuário com 0 visualizações encontrado.")
        return

    print("Usuários com 0 visualizações:")
    for user in zero_view_users:
        print(user)

    resposta = input("Deseja recheckar esses usuários? (s/n): ")
    if resposta.lower() == 's':
        num_instances = len(drivers)
        user_chunks = [zero_view_users[i::num_instances] for i in range(num_instances)]

        threads = []
        results = {}

        def recheck_user_chunk(driver, users_chunk, days, concurso):
            for user in users_chunk:
                try:
                    user, views = scrape_user(driver, user, days, concurso)
                    results[user] = views
                except Exception as e:
                    print(f"Erro ao processar o canal {user}: {e}")

        for i in range(num_instances):
            thread = threading.Thread(target=recheck_user_chunk, args=(drivers[i], user_chunks[i], days, concurso))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        with open(f"database/{concurso}/results/ShortsResults.txt", "w", encoding="utf-8") as file:
            for line in lines:
                user = line.split(" - ")[0]
                if user in results:
                    file.write(f"{user} - Shorts: {results[user]}\n")
                else:
                    file.write(line)

def perguntar_acao_inicial():
    resposta = input("Deseja iniciar um novo check ou verificar os usuários com 0 visualizações? (novo/verificar): ")
    return resposta.lower()

def run_scrape(driver, users, days, result_file, concurso):
    scrape_users(driver, users, days, result_file, concurso)
    driver.quit()

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

def main():
    start_time = time.time()
    service = Service()

    concurso = input("Digite o nome do concurso: ")
    verificar_ou_criar_pastas(concurso)

    num_instances = int(input("Digite o número de instâncias do Chrome para iniciar: ")) 

    drivers = []
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
            options.add_argument("--window-size=1920,1080")
            
            # Configuração do Chrome usando webdriver-manager
            service = ChromeService(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            drivers.append(driver)

        with open(f"database/{concurso}/users/usersYt.txt", "r", encoding="utf-8") as file:
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

        acao_inicial = perguntar_acao_inicial()

        if acao_inicial == "verificar":
            recheck_zero_views(drivers, days, concurso)
        else:
            user_chunks = [[] for _ in range(num_instances)]
            for i, user in enumerate(users):
                user_chunks[i % num_instances].append(user)

            threads = []
            for i in range(num_instances):
                thread = threading.Thread(
                    target=run_scrape,
                    args=(drivers[i], user_chunks[i], days, f"database/{concurso}/results/ShortsResults.txt", concurso)
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            threads = []
            for i in range(num_instances):
                thread = threading.Thread(
                    target=verificar_usuarios_com_zero_views,
                    args=(drivers[i], user_chunks[i], days, f"database/{concurso}/results/ShortsResults.txt", concurso)
                )
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

    except Exception as e:
        print(f"Erro durante a execução: {e}")
    finally:
        for driver in drivers:
            try:
                driver.quit()
            except:
                pass

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nTempo total de execução: {elapsed_time:.2f} segundos")
    input("\nPressione Enter para fechar o programa...")

if __name__ == "__main__": 
    main()