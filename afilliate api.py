from json import loads
from os import mkdir, environ, fsync, sep as directory_separator, getcwd, path, scandir
from threading import Thread, Lock
from time import strftime, sleep, time, strptime
from urllib import parse
from webbrowser import open as browser_open

from certifi import where
from playsound import playsound
from requests import Session, get

environ['REQUESTS_CA_BUNDLE'] = where()


class UdemyScrapper:
    __CATEGORIES_IDS = {
        'Business': [
            'Entrepreneurship',
            'Communication',
            'Management',
            'Sales',
            'Business Strategy',
            'Operations',
            'Project Management',
            'Business Law',
            'Business Analytics & Intelligence',
            'Human Resources',
            'Industry',
            'E-Commerce',
            'Media',
            'Real Estate',
            'Other Business'
        ],
        'Design': [
            'Web Design',
            'Graphic Design & illustration',
            'Design Tools',
            'User Experience Design',
            'Game Design',
            '3D & Animation',
            'Fashion Design',
            'Architectural Design',
            'Interior Design',
            'Other Design'
        ],
        'Development': [
            'Web Development',
            'Data Science',
            'Mobile Development',
            'Programming Languages',
            'Game Development',
            'Database Design & Development',
            'Software Testing',
            'Software Engineering',
            'Software Development Tools',
            'No-Code Development'
        ],
        'Finance & Accounting': [
            'Accounting & Bookkeeping',
            'Compliance',
            'Cryptocurrency & Blockchain',
            'Economics',
            'Finance',
            'Finance Cert & Exam Analysis',
            'Financial Modeling & Analysis',
            'Investing & Trading',
            'Money Management Tools',
            'Taxes',
            'Other Finance & Accounting'
        ],
        'Health & Fitness': [
            'Fitness',
            'General Health',
            'Sports',
            'Nutrition & Diet',
            'Yoga',
            'Mental Health',
            'Martial Arts & Self Defense',
            'Safety & First Aid',
            'Dance',
            'Meditation',
            'Other Health & Fitness'
        ],
        'IT & Software': [
            'IT Certifications',
            'Network & Security',
            'Hardware',
            'Operating Systems & Servers',
            'Other IT & Software'
        ],
        'Lifestyle': [
            'Arts & Crafts',
            'Beauty & Makeup',
            'Esoteric Practices',
            'Food & Beverage',
            'Gaming',
            'Home Improvement & Gardening',
            'Pet Care & Training',
            'Travel',
            'Other Lifestyle'
        ],
        'Marketing': [
            'Digital Marketing',
            'Search Engine Optimization',
            'Social Media Marketing',
            'Branding',
            'Marketing Fundamentals',
            'Marketing Analytics & Automation',
            'Public Relations',
            'Paid Advertising',
            'Video & Mobile Marketing',
            'Content Marketing',
            'Growth Hacking',
            'Affiliate Marketing',
            'Product Marketing',
            'Other Marketing'
        ],
        'Music':[
            'Instruments',
            'Music Production',
            'Music Fundamentals',
            'Vocal',
            'Music Techniques',
            'Music Software',
            'Other Music'
        ],
        'Office Productivity': [
            'Microsoft',
            'Apple',
            'Google',
            'SAP',
            'Oracle',
            'Other Office Productivity'
        ],
        'Personal Development': [
            'Personal Transformation',
            'Personal Productivity',
            'Leadership',
            'Career Development',
            'Parenting & Relationships',
            'Happiness',
            'Esoteric Practices',
            'Religion & Spirituality',
            'Personal Brand Building',
            'Creativity',
            'Influence',
            'Self Esteem & Confidence',
            'Stress Management',
            'Memory & Study Skills',
            'Motivation',
            'Other Personal Development'
        ],
        'Photography & Video': [
            'Digital Photography',
            'Photography',
            'Portrait Photography',
            'Photography Tools',
            'Commercial Photography',
            'Video Design',
            'Other Photography & Video'
        ],
        'Teaching & Academics': [
            'Engineering',
            'Humanities',
            'Math',
            'Science',
            'Online Education',
            'Social Science',
            'Language Learning',
            'Teacher Training',
            'Test Prep',
            'Other Teaching & Academics'
        ]
    }

    __BASE_URL = 'https://www.udemy.com'
    __API_URL = "/api-2.0/courses/?category={category}&language=en&subcategory={subcategory}" \
                "&ordering=newest&page=1&page_size=100&fields[course]=url,title,created,is_practice_test_course"

    __Threads_POOL = []
    __WRITING_CONTAINER = {}
    __THREAD_LOCKER = Lock()
    __DISCOVERED_URLS = {}
    __COURSES_COUNT = {}
    __STOP_SCRAPPING = {}
    __WATCHER_THREAD = None
    __STOP_TIME = 0
    __CATEGORY = "*"
    __STOP_PRINTING = False
    __TOTAL_STOP = False
    __WAITING_TIME = 0
    __ACCESS_TOKEN_UPDATED = False
    
    @staticmethod
    def course_found_writer(writer, course_title, course_url):
        writing_form = "".center(50, '-') + "\n"
        writing_form += f"Title: {course_title}\n"
        writing_form += f"Url: https://www.udemy.com{course_url}\n"
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

    @staticmethod
    def set_access_token(session):
        access_token = input("Please enter access token: ")
        try:
            cookies = {
                'access_token': access_token
            }
            url = 'https://www.udemy.com/api-2.0/courses/'
            resp = get(url, cookies=cookies)
            if resp.status_code != 200:
                print("[-] Invalid Access Token Given, script will exit")
                exit(0)
            session.cookies.update(cookies)
            return True
        except:
            print("[-] Can't connect to the website, script will exit")
            return False

    def __thread_checker(self):
        stop = all([subcategory for subcategory in self.__STOP_SCRAPPING.values()])
        while not stop or self.__Threads_POOL:
            try:
                with self.__THREAD_LOCKER:
                    for thread in self.__Threads_POOL:
                        if not thread.is_alive():
                            self.__Threads_POOL.remove(thread)
                stop = all([subcategory for subcategory in self.__STOP_SCRAPPING.values()])
            except KeyboardInterrupt:
                self.__console_log("[-] system will exit clearing resources")
                self.__STOP_PRINTING = True
                self.__TOTAL_STOP = True

        stop = False
        self.__STOP_PRINTING = False
        while not stop:
            for category in self.__CATEGORIES_IDS:
                try:
                    if not self.__WRITING_CONTAINER[category].closed:
                        self.__console_log(f'[+] closing {category} file')
                        self.__WRITING_CONTAINER[category].flush()
                        fsync(self.__WRITING_CONTAINER[category])
                        self.__WRITING_CONTAINER[category].close()
                        self.__console_log(f'[+] closed {category} file')
                except KeyboardInterrupt:
                    break
            else:
                stop = True

    def __console_log(self, message):
        with self.__THREAD_LOCKER:
            if not self.__STOP_PRINTING:
                print(message, f"threads count: {self.__Threads_POOL.__len__()}, "
                               f"searching date: {strftime('%Y-%m-%d', self.__date)}")

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
            

    def __init__(self):
        self.__session = Session()
        if not self.set_access_token(self.__session):
            exit(0)
        date = input("Please enter date ex (Year-Month-Day): ")
        try:
            self.__date = strptime(date, "%Y-%m-%d")
        except:
            print("[-] invalid date used, script will exit")
            exit(0)

        category = input("Please enter category, press enter for all: ")

        if category and category not in self.__CATEGORIES_IDS:
            print("[-] invalid category used, script will exit")
            exit(0)

        self.__CATEGORY = category if category else '*'
        self.__session.proxies.update({
            'http': 'socks5://Selengahmedredaahmed:G2l5ReA@191.101.148.218:45786',
            'https': 'socks5://Selengahmedredaahmed:G2l5ReA@191.101.148.218:45786'
        })

    def scrape(self):
        self.__CATEGORIES_IDS = self.__CATEGORIES_IDS if self.__CATEGORY == '*' else {self.__CATEGORY: self.__CATEGORIES_IDS[self.__CATEGORY]}
        while not self.__TOTAL_STOP:
            watcher_thread = Thread(daemon=True, name='watcher_thread', target=self.__thread_checker, args=())

            for (category, subcategories) in self.__CATEGORIES_IDS.items():
                self.__STOP_SCRAPPING[category] = {}
                self.__COURSES_COUNT[category] = {}
                for subcategory in subcategories:
                    self.__COURSES_COUNT[category].update({subcategory: 0, f'{subcategory}_counter': 0})
                    self.__STOP_SCRAPPING[category][subcategory] = False
                    self.__scrape(category, subcategory)
            while True:
                try:
                    watcher_thread.start()
                    watcher_thread.join()
                    break
                except RuntimeError:
                    pass
                except KeyboardInterrupt:
                    self.__TOTAL_STOP = True

            self.__date = strptime(strftime("%Y-%m-%d"), "%Y-%m-%d")
            sleep(60)

    def __scrape(self, category, subcategory):
        try:
            mkdir(f"{getcwd()}{directory_separator}searches")
        except FileExistsError:
            pass

        self.__WRITING_CONTAINER[category] = open(
            f"{getcwd()}{directory_separator}searches{directory_separator}{strftime('%Y-%m-%d', self.__date)}.txt",
            "a+", encoding="utf-8", errors='ignore')
        printed = False
        while True:
            try:
                thread = Thread(target=self.__get_page, args=(category, subcategory))
                thread.start()
                self.__Threads_POOL.append(thread)
                break
            except RuntimeError:
                if not printed:
                    self.__console_log('[-] unable to make thread, waiting for free slots')
                    printed = True

    def __get_page(self, category_name, subcategory):
        base_url = self.__BASE_URL + self.__API_URL.format(category=parse.quote(category_name),
                                                           subcategory=parse.quote(subcategory))
        while not self.__STOP_SCRAPPING[category_name][subcategory] and not self.__TOTAL_STOP:
            try:
                while time() - self.__STOP_TIME < self.__WAITING_TIME:
                    continue
                resp = self.__session.get(base_url)
                if resp.status_code == 200:
                    self.__ACCESS_TOKEN_UPDATED = False
                    resp = loads(resp.text)
                    self.__COURSES_COUNT[category_name][subcategory] = resp['count']

                    self.__console_log(f"[+] {self.__COURSES_COUNT[category_name][subcategory + '_counter']}"
                                       f"/{self.__COURSES_COUNT[category_name][subcategory]} -> "
                                       f"getting data from {category_name}")

                    if resp['next'] is None:
                        self.__STOP_SCRAPPING[category_name][subcategory] = True
                    else:
                        base_url = resp['next']
                    while True:
                        try:
                            with self.__THREAD_LOCKER:
                                validation_thread = Thread(target=self.__courses_validator, args=(resp['results'],
                                                                                                  category_name,
                                                                                                  subcategory))
                                validation_thread.start()
                                self.__Threads_POOL.append(validation_thread)
                            break
                        except:
                            pass
                        
                elif resp.status_code == 429:
                    self.__WAITING_TIME = int(resp.text.split(' ')[-2])
                    self.__console_log(f'[-] last request has been blocked, trying after {self.__WAITING_TIME} seconds')
                    if not self.__ACCESS_TOKEN_UPDATED:
                        with self.__THREAD_LOCKER:
                            change_access_token = input('[+] for changing access token press y: ')
                            if change_access_token.lower() == 'y':
                                if not self.set_access_token(self.__session):
                                    self.__TOTAL_STOP = True
                                    exit(0)
                                else:
                                    self.__WAITING_TIME = 0
                                    self.__ACCESS_TOKEN_UPDATED = True
                            else:
                                print(f"[+] Waiting for {self.__WAITING_TIME} seconds")
                                self.__STOP_TIME = time()
                                sleep(self.__WAITING_TIME)
                else:
                    self.__console_log('[-] this account has been disabled, script will exit try to contact with dev.')
                    self.__TOTAL_STOP = True
                    exit(0)

            except Exception as e:
                self.__console_log(
                    f"[-] An error occurred while connecting to the website, the scrapper will stop, {e}")
                exit(0)

    def __courses_validator(self, results, category_name, subcategory):
        for course in results:
            if course['url'] not in self.__DISCOVERED_URLS and not course['is_practice_test_course'] and course['is_paid']:
                creation_time = str(course['created']).split("T")[0]
                creation_time = strptime(creation_time, "%Y-%m-%d")
                self.__COURSES_COUNT[category_name][f"{subcategory}_counter"] += 1

                if creation_time < self.__date:
                    self.__STOP_SCRAPPING[category_name][subcategory] = True
                    continue

                self.__console_log(f"[+] {self.__COURSES_COUNT[category_name][subcategory + '_counter']}"
                                   f"/{self.__COURSES_COUNT[category_name][subcategory]} -> "
                                   f"a new course is found -> {category_name} -> {subcategory}")
                self.course_found_writer(self.__WRITING_CONTAINER[category_name], course['title'], course['url'])
                with self.__THREAD_LOCKER:
                    browser_open("https://www.udemy.com" + course['url'], False, False)
                    try:
                        playsound(f"{getcwd()}{directory_separator}Alert.wav")
                    except Exception:
                        pass
                    self.__DISCOVERED_URLS.append(self.__BASE_URL + course['url'])


scrapper = UdemyScrapper()
scrapper.scrape()
input("press any key to stop")
