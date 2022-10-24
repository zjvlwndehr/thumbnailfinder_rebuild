from __future__ import division
from pkgutil import ImpImporter
from flask import *
from flask_compress import Compress
import os
import json
from parse import parse
from threading import Thread
import cv2
from yt_dlp import YoutubeDL
import numpy as np
from requests import get
class DEBUG:
    def log(self, log):
        print("[DEBUG] " + log)
        f = open("debug.log", "r")
        data = f.read()
        f.close()
        f = open("debug.log", "w")
        f.write(data + "\n[DEBUG] " + log)
        f.close()
debug = DEBUG()

class NETWORK:
    def __init__(self):
        self.ip_list = []
        self.work_list = {}
    
    def add_ip(self, ip):
        self.ip_list.append(ip)
        debug.log("Added IP " + ip + " to queue")
    
    def pop_ip(self, ip):
        self.ip_list.remove(ip)
        debug.log("Removed IP " + ip + " from queue")

network = NETWORK()

class WORK:
    def __init__(self):
        self.ytdl = YoutubeDL()

    def id_maker(self, url) -> str:
        if "youtube.com" in str(url):
            return parse("{}?v={id}", url)["id"]
        elif "youtu.be" in str(url):
            return parse("youtu.be/{}", url)["id"]
        else:
            return None

    def url_maker(self, id:str, time:int) -> str:
        if time == 0:
            return "http://youtu.be/" + id
        else:
            return "http://youtu.be/" + id + "?t=" + str(time)

    def search(self, id:str) -> str:
        with open("data.json", "r") as f:
            data = json.load(f)
            try:
                debug.log("Search for " + id + " in data.json")
                debug.log("Show data.json" + str(data))
                for i in data:
                    if id in i:
                        debug.log("Found " + id + " in data.json at " + i)
                        return i[id]
                debug.log("Error: search(); Not Found")            
                return None
            except:
                debug.log("Error: except search(); Not Found")
                return None

    def processstart(self, url:str, ip:int) -> int:
        thread = Thread(target=self.download, args=(url, ip,))
        thread.start()
        thread.join()
        result = 0
        thread = Thread(target=self.analyze, args=(url, result))
        thread.start()
        thread.join()
        # result = self.analyze(url)
        network.pop_ip(ip)
        debug.log(f"Result for {self.id_maker(url)} is {self.url_maker(self.id_maker(url), result)}")
        return self.search(self.id_maker(url))

    def download(self, url:str, ip:int) -> None:
        ls = os.listdir()
        id = self.id_maker(url)
        info = self.ytdl.extract_info(url, download=False)
        title = info['title']

        if id + ".mp4" in ls:
            debug.log("File " + id + ".mp4 already exists")
            debug.log("Download " + url + " for IP " + ip + " finished")
        else:
            for i in ls:
                if i.endswith(".mp4") and id in i:
                    os.rename(i, id + ".mp4")
                    debug.log("File " + id + ".mp4 renamed")
                    debug.log("Download " + url + " for IP " + ip + " finished")
                else:
                    self.ytdl.download(url)
                    ls = os.listdir()
                    for j in ls:
                        if j.endswith(".mp4") and id in j:
                            os.rename(j, id + ".mp4")
                            debug.log(f"Rename {j} to {id}.mp4")
                        debug.log("Download " + url + " for IP " + ip + " finished")

        # download webp image
        # convert webp to jpg
        debug.log("Analyze " + url + " started")
        id = self.id_maker(url)
        
        if id + ".jpg" in os.listdir():
            debug.log("File " + id + ".jpg already exists")
        else:
            thumbnail = self.ytdl.extract_info(url, download=False)['thumbnail']
            # os.system(f"curl {thumbnail} > {id}.jpg")
            with open(id + ".jpg", "wb") as f:
                f.write(get(thumbnail).content)
            debug.log("Downloaded " + id + ".jpg")

    def analyze(self, url, result) -> int:
        
        id = self.id_maker(url)
        # SIFT algorithm and knnmatch()
        sift = cv2.SIFT_create()
        kpt0, des0 = sift.detectAndCompute(cv2.imread(f'./{id}.jpg', cv2.IMREAD_GRAYSCALE), None)
        debug.log("Analyze thumbnail " + id + " finished")

        vidcap = cv2.VideoCapture("./" + id + ".mp4")

        division_for_modulus = 30
        cnt = 0
        good = []
        work = []

        debug.log("Parsing video " + id + " started")
        
        while(vidcap.isOpened()):
            success, image = vidcap.read()
            if success == False:
                break
            if cnt % division_for_modulus == 0 and success:
                work.append(image)
            cnt += 1
        vidcap.release()
        cv2.destroyAllWindows()
        debug.log("Parsing video " + id + " finished")            

        ## multi-threading
        thread = []
        rtn = []
        thread_count = 8
        greedy_work = []
        greedy_work_constant = 10
        ## Greedy Algorithm
        debug.log("Greedy Algorithm started")
        for i in range(0, len(work) // greedy_work_constant):
            greedy_work.append(work[i * greedy_work_constant])

        debug.log("Greedy Count: " + str(len(greedy_work)))
        ## find good matches in big scope
        for i in range(0, thread_count):
            debug.log("Greedy " + id + " thread " + str(i) + " started")
            thread.append(Thread(target=self.analyze_thread, args=(i, greedy_work[i*(len(greedy_work)//thread_count):(i+1)*(len(greedy_work)//thread_count)], des0, sift, rtn)))
            thread[i].start()
        for i in range(0, thread_count):
            thread[i].join()
        debug.log(f"Greedy Algorithm finished")
        debug.log(f"Greedy Result: {rtn}")
        cnt = 0
        max = 0
        key = 0
        key_cnt = 0
        keys = list(rtn[0].keys())[0]
        print(keys)
        for thread_id in range(0, thread_count):
            for i in rtn[thread_id].values():
                cnt = 0
                for j in i:
                    if j > max:
                        max = j
                        key = list(rtn[thread_id].keys())[0]
                        key_cnt = cnt
                        #debug.log(f"max: {max}, key: {key}, key_cnt: {key_cnt}, values: {rtn[thread_id].values()}")
                    cnt += 1    

        # debug.log(f"max: {max}, key: {key}, key_cnt: {key_cnt}, thread_count: {thread_count}")
        # max_matches_frame = int(((len(greedy_work) / thread_count) * key + key_cnt) * greedy_work_constant)
        max_matches_frame = int(division_for_modulus * greedy_work_constant) * key_cnt
        max_matches_frame_to_t = max_matches_frame // int(division_for_modulus * greedy_work_constant)
        debug.log(f"Max matches frame: {max_matches_frame}")
        debug.log(f"Max matches frame to t: {max_matches_frame_to_t}")

        thread = []
        rtn = []
        thread_count = 8
        greedy_work = []

        # ## find best result from local result
        # for i in range(0, thread_count):
        #     debug.log("Analyze " + id + " thread " + str(i) + " started")
        #     thread.append(Thread(target=self.analyze_thread, args=(i, work[i*(len(work)//thread_count):(i+1)*(len(work)//thread_count)], des0, sift, rtn)))
        #     thread[i].start()
        # for i in range(0, thread_count):
        #     thread[i].join()


        # # find max value
        # max = 0
        # key = 0
        # key_cnt = 0
        # frame_rate = 30

        # for thread_id in range(0, thread_count):
        #     for i in rtn[thread_id].values():
        #         cnt = 0
        #         for j in i:
        #             if j > max:
        #                 max = j
        #                 key = thread_id
        #                 key_cnt = cnt
        #             cnt += 1    
         
        # max_matches_frame_to_t= int(((len(work)//thread_count) * division_for_modulus * key + key_cnt * division_for_modulus) / frame_rate) 
        
        # print(f"max_matches_frame_to_t : {max_matches_frame_to_t}")

        # save data
        if self.search(id) != None:
            pass
        else:
            with open("data.json", "r") as f:
                data = json.load(f)
            data.append({id: max_matches_frame_to_t})
            with open("data.json", "w") as f:
                json.dump(data, f)

        debug.log("Analyze " + id + " finished")
        debug.log("Return result for " + id + " is " + str(max_matches_frame_to_t))

    def analyze_thread(self, thread_id, work, des0, sift, rtn):
        good = []
        for image in work:
            # print(f"Thread {thread_id} analyzing frame")
            cnt = 0
            try:
                _, des1 = sift.detectAndCompute(image, None)
                bf = cv2.BFMatcher()
                matches = bf.knnMatch(des0, des1, k=2)
                
                for m, n in matches:
                    if m.distance < 0.3 * n.distance:
                        cnt += 1
            except:
                pass
            good.append(cnt)
        rtn.append(dict.fromkeys([thread_id], good))
        debug.log("Analyze thread " + str(thread_id) + " finished")

    def work(self, ip):
        thread = []
        URL = "http://youtu.be/" + network.work_list[ip]            
        debug.log("Download " + URL + " for IP " + ip + " started")
        self.ytdl.download([URL])
        # extract thumbnail
        info = self.ytdl.extract_info(URL, download=False)
        thumbnail = info['thumbnail']
        debug.log("Thumbnail " + URL + " for IP " + ip + " started")

    def work_test(self, id, *img_list):
        f = open("data.json", "r")
        data = json.loads(f.read())
        f.close()

        if data[id] != '':
            return data[id]
        else:
            URL = "http://youtu.be/" + id  
            self.ytdl.download([URL])
            info = self.ytdl.extract_info(URL, download=False)
            thumbnail = info['thumbnail']

            vidcap = cv2.VideoCapture("./" + id + ".mp4")
            while(vidcap.isOpened()):
                if(int(vidcap.get(1)) % 3 == 0):
                    success, image = vidcap.read()
                    img_list.append(image)
          
work = WORK()

app = Flask(__name__)
app.secret_key = os.urandom(12)
compress = Compress(app)
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload')
def upload():
    # GET request
    ip = request.remote_addr
    try:
        if ip in network.ip_list:
            return {"status":200, "resp":"You are already in queue"}, 200
        if ip not in network.ip_list:
            arg = request.args['value']
            debug.log(f"[{ip} request] : {arg}")
            if "youtube.com" in str(arg):
                id = parse("{}?v={id}", arg)["id"]
                debug.log(f"[{ip} request] Youtube video ID: {id}")
                network.add_ip(ip)
                debug.log(f"[{ip} request] Added to queue")
                answer = None
                answer = work.search(id)
                debug.log(f"[{ip} request] Search result: {answer}")
                if answer != None:
                    network.pop_ip(ip)
                    debug.log(f"[{ip} request] Removed from queue")
                    return {"status":200, "resp":work.url_maker(id, answer)}, 200
                elif answer == None:
                    debug.log(f"[{ip} request] Not found in database")
                    result = work.processstart(arg, ip)
                    network.pop_ip(ip)
                    debug.log(f"[{ip} request] Removed from queue")
                    return {"status":200, "resp":work.url_maker(id, result)}, 200
                # return {"status":200, "resp":"test"}, 200
            elif "youtu.be" in str(arg):
                id = parse("youtu.be/{}", arg)["id"]
                debug.log(f"[{ip} request] Youtube video ID: {id}")
                network.add_ip(ip)
                if answer != None:
                    network.pop_ip(ip)
                    return {"status":200, "resp":work.url_maker(id, answer)}, 200
                else:
                    result = work.processstart(arg, ip)
                    network.pop_ip(ip)
                    return {"status":200, "resp":work.url_maker(id, result)}, 200
            else:
                debug.log(f"[{ip} request] Invalid URL 400")
                network.pop_ip(ip)
                return {"status":400, "resp":"Invalid URL"}, 400
    except:
        return render_template('error.html'), 400

@app.route('/return')
def check():
    ip = request.remote_addr
    arg = request.args['value']

    if ip in network.ip_list:
        id = work.id_maker(network.work_list[ip])
    try:
        if ip in network.ip_list:
            return {"status":200, "resp":"working"}, 200
        else:

            return {"status":200, "resp":"done"}, 200
    except:
        return render_template('error.html'), 400

@app.route('/download')
def download():
    value = request.args['value']
    id = parse("{}", value)["id"]
    work.download()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)