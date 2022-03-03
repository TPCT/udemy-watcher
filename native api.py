from json import loads
from os import mkdir, environ, fsync, path, sep as directory_separator, getcwd, scandir
from queue import Queue
from threading import Thread, Lock
from time import strptime, sleep, time, mktime
from webbrowser import open as browser_open

from certifi import where
from playsound import playsound
from requests import Session

environ['REQUESTS_CA_BUNDLE'] = where()


class UdemyScrapper:
    __CATEGORIES_IDS = {
        'Business': [
            26,
            28,
            30,
            32,
            34,
            36,
            38,
            40,
            44,
            48,
            50,
            354,
            52,
            58,
            60
        ],
        'Design': [
            6,
            110,
            112,
            114,
            116,
            120,
            122,
            124,
            128,
            130
        ],
        'Development': [
            8,
            558,
            10,
            12,
            14,
            16,
            18,
            20,
            362,
            575
        ],
        'Finance & Accounting': [
            530,
            532,
            534,
            536,
            540,
            542,
            544,
            546,
            548,
            550,
            552
        ],
        'Health & Fitness': [
            222,
            224,
            226,
            228,
            230,
            232,
            236,
            238,
            240,
            242,
            244
        ],
        'IT & Software': [
            132,
            134,
            136,
            138,
            140
        ],
        'Lifestyle': [
            180,
            184,
            577,
            182,
            188,
            190,
            192,
            186,
            194
        ],
        'Marketing': [
            62,
            64,
            66,
            68,
            70,
            72,
            74,
            76,
            78,
            80,
            86,
            88,
            90,
            94
        ],
        'Music': [
            296,
            298,
            300,
            302,
            304,
            306,
            308
        ],
        'Office Productivity': [
            96,
            98,
            100,
            102,
            106,
            108
        ],
        'Personal Development': [
            142,
            144,
            146,
            150,
            152,
            156,
            577,
            158,
            160,
            164,
            166,
            168,
            170,
            172,
            176,
            178
        ],
        'Photography & Video': [
            370,
            196,
            204,
            198,
            208,
            218,
            220
        ],
        'Teaching & Academics': [
            366,
            380,
            310,
            312,
            523,
            376,
            521,
            527,
            529,
            525
        ]
    }
    __BASE_URL = "https://www.udemy.com/api-2.0/discovery-units/all_courses/?page_size=60&subcategory=" \
                 "&instructional_level=&lang=en&price=&duration=&closed_captions=" \
                 "&subs_filter_type=&sort=newest&" \
                 "subcategory_id={subcategory_id}&source_page=subcategory_page&locale=en_US" \
                 "&currency=egp&navigation_locale=en_US&skip_price=true&sos=ps&fl=scat"

    __NEXT_PAGE = {}
    __Threads_POOL = []
    __WRITING_CONTAINER = None
    __THREAD_LOCKER = Lock()
    __DISCOVERED_URLS = {}
    __STOP_SCRAPPING = {}
    __STOP_TIME = 0
    __CATEGORY = "*"
    __SELECTOR = ""
    __SAVING_PATH = getcwd() + directory_separator + "searches"

    @staticmethod
    def get_next(response: dict):
        try:
            return f"https://www.udemy.com{response['pagination']['next']['url']}"
        except:
            return None

    @staticmethod
    def course_found_writer(writer, publish_time, creation_time, last_updated_time, course_title, course_url):
        writing_form = "".center(50, '-') + "\n"
        writing_form += f"Created at: {creation_time}\n"
        writing_form += f"Published at: {publish_time}\n"
        writing_form += f"Last Updated at: {last_updated_time}\n"
        writing_form += f"Title: {course_title}\n"
        writing_form += f"Url: {course_url}\n"
        UdemyScrapper.writer(writer, writing_form)

    @staticmethod
    def writer(writer, message, unique=False):
        with UdemyScrapper.__THREAD_LOCKER:
            if unique:
                writer.seek(0)
                content = writer.read()
                if message in content:
                    return
            writer.write(message)
            writer.flush()
            fsync(writer)

    def verify(self, creation_date, publish_date, last_updated_date, target_date, course_url):
        data = self.__DISCOVERED_URLS.get(course_url)
        if data is not None and (creation_date == data['creation time'] or last_updated_date == data['last update time'] or publish_date == data['publish time']):
            return 1

        creation_date = mktime(strptime(creation_date, "%Y-%m-%d")
                               if creation_date else strptime("1990-01-01", "%Y-%m-%d"))
        publish_date = mktime(strptime(publish_date, "%Y-%m-%d")
                              if publish_date else strptime("1990-01-01", "%Y-%m-%d"))
        last_updated_date = mktime(strptime(last_updated_date, "%Y-%m-%d")
                                   if last_updated_date else strptime("1990-01-01", "%Y-%m-%d"))
        target_date = mktime(strptime(target_date, "%Y-%m-%d"))

        status = {
            "creation": lambda: target_date <= creation_date,
            "publish": lambda: target_date <= publish_date,
            "last_updated": lambda: last_updated_date >= target_date,
            "all": lambda: target_date <= creation_date or target_date <= publish_date or last_updated_date >= target_date,
        }

        if status[self.__SELECTOR]():
            return 0

    def __thread_checker(self):
        stop = all([all(x.values()) for x in self.__STOP_SCRAPPING.values()])
        while not stop or self.__Threads_POOL:
            if stop and self.__Threads_POOL:
                self.__console_log("waiting for threads execution")
            with self.__THREAD_LOCKER:
                for thread in self.__Threads_POOL:
                    if not thread.is_alive():
                        self.__Threads_POOL.remove(thread)
            stop = all([all(x.values()) for x in self.__STOP_SCRAPPING.values()])

        if not self.__WRITING_CONTAINER.closed:
            self.__WRITING_CONTAINER.flush()
            fsync(self.__WRITING_CONTAINER)
            self.__WRITING_CONTAINER.close()

    def __console_log(self, message):
        with self.__THREAD_LOCKER:
            print(message, f"threads count: {self.__Threads_POOL.__len__()}")

    def __init__(self):
        self.date = input("Please enter date ex (Year-Month-Day): ")
        category = input("Please enter category, press enter for all: ")
        if category and category not in self.__CATEGORIES_IDS.keys():
            print("[-] invalid category used, script will exit")
            exit(0)

        self.__CATEGORY = category if category else '*'

        selector = input("1: for creation time\n2: for publish time\n3: for last updated time\n4: for all\nChoice:")
        selector_keys = {
            "1": "creation",
            "2": "publish",
            "3": "last_updated",
            "4": "all"
        }
        if selector in selector_keys.keys():
            self.__SELECTOR = selector_keys[selector]
        else:
            print("[-] invalid number, script will exit")
            exit(0)

        try:
            strptime(self.date, "%Y-%m-%d")
        except:
            print("[-] Invalid date format entered please try again, scrapper will exit")
            exit(0)

        self.real_time = input("Please enter (y) for real time: ")

        if self.real_time.lower() == "y":
            self.real_time = True
        else:
            self.real_time = False
        self.__session = Session()
        self.__session.proxies.update({
            'http': 'socks5://Selengahmedredaahmed:G2l5ReA@191.101.148.218:45786',
            'https': 'socks5://Selengahmedredaahmed:G2l5ReA@191.101.148.218:45786'
        })
        
        print("[+] reading files...")
        self.load_files()

    def load_files(self):
        creation_time = None
        publish_time = None
        last_update_time = None
        title = None
        url = None
        files = None
        if path.isdir(self.__SAVING_PATH):
            files = scandir(self.__SAVING_PATH)
            
        for file in files:
            if path.isfile(file.path):
                with open(file.path, "r+") as reader:
                    for line in reader:
                        line = line.lower()
                        if line == "-"*50:
                            continue
                        elif line.startswith("created at: "):
                            creation_time = line["created at: ".__len__(): -1]
                        elif line.startswith("published at: "):
                            publish_time = line["published at: ".__len__(): -1]
                        elif line.startswith("last updated at: "):
                            last_update_time = line["last updated at: ".__len__(): -1]
                        elif line.startswith("title: "):
                            title = line["title: ".__len__(): -1]
                        elif line.startswith("url: "):
                            url = line["url: ".__len__(): -1]
                            self.__DISCOVERED_URLS[url] = {
                                "creation time": creation_time,
                                "publish time": publish_time,
                                "last update time": last_update_time,
                                "title": title
                            }
                            
                            creation_time = None
                            publish_time = None
                            last_update_time = None
                            title = None,
                            url = None
        
    def scrape(self):
        first_time = not self.real_time
        while self.real_time or first_time:
            if self.__CATEGORY == '*':
                for (category, subcategories) in self.__CATEGORIES_IDS.items():
                    self.__STOP_SCRAPPING[category] = {}
                    self.__NEXT_PAGE[category] = {}
                    for subcategory in subcategories:
                        self.__STOP_SCRAPPING[category][subcategory] = False
                        self.__NEXT_PAGE[category][subcategory] = Queue()
                            
                        while True:
                            try:
                                with self.__THREAD_LOCKER:
                                    thread = Thread(daemon=True, name=subcategory, target=self.__scrape,
                                                    args=(category, subcategory))
                                    thread.start()
                                    self.__Threads_POOL.append(thread)
                                    break
                            except RuntimeError:
                                self.__console_log("[-] Trying to create new thread, __scrape")
            else:
                self.__STOP_SCRAPPING[self.__CATEGORY] = {}
                self.__NEXT_PAGE[self.__CATEGORY] = {}
                    
                for subcategory in self.__CATEGORIES_IDS[self.__CATEGORY]:                    
                    self.__STOP_SCRAPPING[self.__CATEGORY][subcategory] = False
                    self.__NEXT_PAGE[self.__CATEGORY][subcategory] = Queue()
                        
                    while True:
                        try:
                            with self.__THREAD_LOCKER:
                                thread = Thread(daemon=True, name=subcategory, target=self.__scrape,
                                                args=(self.__CATEGORY, subcategory))
                                thread.start()
                                self.__Threads_POOL.append(thread)
                                break
                        except RuntimeError:
                            self.__console_log("[-] Trying to create new thread, __scrape")

            while True:
                try:
                    watcher_thread = Thread(daemon=True, name='watcher_thread', target=self.__thread_checker, args=())
                    watcher_thread.start()
                    watcher_thread.join()
                    break
                except RuntimeError:
                    pass

    def __scrape(self, category, subcategory):
        try:
            mkdir(f"{getcwd()}{directory_separator}searches")
        except FileExistsError:
            pass

        self.__WRITING_CONTAINER = open(f"{self.__SAVING_PATH}{directory_separator}{self.date}.txt",
                                        "a+", encoding="utf-8", errors='ignore')
        stop = False
        while not stop:
            if time() - self.__STOP_TIME < 5:
                continue

            stop = self.__get_page(category, subcategory)

    def __get_page(self, category_name, subcategory):
        base_url = self.__BASE_URL.format(subcategory_id=subcategory) \
            if not self.__NEXT_PAGE[category_name][subcategory].qsize() else self.__NEXT_PAGE[category_name][subcategory].get()
        try:
            while time() - self.__STOP_TIME < 5:
                continue

            results = list()
            self.__get_data(base_url, category_name, subcategory, results, True)

            if self.__STOP_SCRAPPING[category_name][subcategory]:
                return True

            for result in results[:-1]:
                while True:
                    try:
                        with self.__THREAD_LOCKER:
                            thread = Thread(daemon=True, target=self.__get_data, args=(result, category_name,
                                                                                       subcategory, list()))
                            thread.start()
                            self.__Threads_POOL.append(thread)
                        break
                    except RuntimeError:
                        self.__console_log("[-] Trying to create new thread after 1 second, __get_page")
                        sleep(1)

            self.__NEXT_PAGE[category_name][subcategory].put_nowait(results[-1])
            return False
        except Exception as e:
            print(f"[-] An error occurred while connecting to the website the scrapper will stop, {e}")
            exit(0)

    def __courses_search(self, courses, category_name, total_pages, current_page):
        for course in courses:
            if not course['is_practice_test_course'] and course['locale']['locale'] == 'en_US' and course['is_paid']:
                url = "https://www.udemy.com" + course['url']
                publish_date = str(course['published_time']).split("T")[0]
                creation_date = str(course['created']).split("T")[0]
                last_updated_date = course['last_update_date']
                verified = self.verify(creation_date, publish_date, last_updated_date, self.date, url)

                if verified == 0:
                    title = course['title']
                    
                    self.__DISCOVERED_URLS[url] = {
                            "creation time": creation_date,
                            "publish time": publish_date,
                            "last update time": last_updated_date,
                            "title": title
                        }
                    
                    self.__console_log(f"[+] New course found -> {title}, "
                                       f"page=({current_page}/{total_pages})@({category_name})")
                    self.course_found_writer(self.__WRITING_CONTAINER, publish_date, creation_date,
                                             last_updated_date, title, url)
                    with self.__THREAD_LOCKER:
                        #browser_open(url, False, False)
                        try:
                            playsound(f"{getcwd()}{directory_separator}Alert.wav")
                        except Exception:
                            pass

    def __get_data(self, base_url, category_name, subcategory, result, append_result=False):
        if self.__STOP_SCRAPPING[category_name][subcategory]:
            self.__console_log(f"[+] done scrapping {category_name}")
            exit(0)

        while True:
            try:
                if time() - self.__STOP_TIME < 5:
                    continue

                resp = self.__session.get(base_url)

                if resp.status_code != 200:
                    self.__console_log(f"[-] Response Blocked, Trying in five seconds")
                    self.__STOP_TIME = time()
                    sleep(5)
                    continue

                resp_json = loads(resp.text)
                resp = resp_json['unit']
                current_page = resp['pagination']['current_page']
                total_pages = resp['pagination']['total_page']

                self.__console_log(f"[+] Searching for courses by this {self.date}, "
                                   f"page=({current_page}/{total_pages})"
                                   f"@({category_name})")

                while True:
                    try:
                        with self.__THREAD_LOCKER:
                            thread = Thread(daemon=True, target=self.__courses_search,
                                            args=(resp['items'], category_name, total_pages, current_page))
                            thread.start()
                            self.__Threads_POOL.append(thread)
                        break
                    except RuntimeError:
                        pass

                if current_page == total_pages:
                    self.__STOP_SCRAPPING[category_name][subcategory] = True
                    self.__console_log(f"[+] done scrapping {category_name}")

                if append_result and not self.__STOP_SCRAPPING[category_name][subcategory]:
                    for page in resp['pagination']['pages']:
                        if page['label'] > current_page:
                            result.append('https://www.udemy.com' + page['url'])
                break
            except Exception:
                pass


UdemyScrapper().scrape()


input("press any key to stop")
