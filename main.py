from astrbot.api.event import filter, AstrMessageEvent, MessageChain, MessageEventResult
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.star import Context, Star, register
from selenium.webdriver.edge.options import Options
from selenium.webdriver.edge.service import Service
from apscheduler.triggers.cron import CronTrigger
from astrbot.api.message_components import Plain
from jinja2 import Environment, BaseLoader
from datetime import datetime
from astrbot.api import logger
from selenium import webdriver
from lxml import html
import configparser
import tempfile
import asyncio
import aiohttp
import base64
import re
import os
class CourseFetcher:
    '''
    课程处理类负责与教务系统进行交互
    '''
    # 教务系统登录URL
    LOGIN_URL = "https://qzjwpc.cqvtu.edu.cn/jsxsd/xk/LoginToXk"
    # 课程表URL格式
    TIMETABLE_URL_FORMAT = "https://qzjwpc.cqvtu.edu.cn/jsxsd/framework/mainV_index_loadkb.htmlx?rq={date}&sjmsValue=7BF92DA627F746F59D245A65B31BCE86&xnxqid=2024-2025-2&xswk=false"
    def __init__(self, username, password, start_date_str):
        '''
           初始化
           :param username: 用户名
           :param password: 密码
           :param start_date_str: 开始日期字符串
        '''
        self.username = username
        self.password = password
        self.start_date_str = start_date_str
        self.edge_options = Options()
        self.edge_options.add_argument("--headless")  # 无头模式
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.driver_path = os.path.join(script_dir, "msedgedriver.exe")
        self.num_map = {
            0: '零',
            1: '一',
            2: '二',
            3: '三',
            4: '四',
            5: '五',
            6: '六',
            7: '七',
        }
        self.TMPL = """<!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {
                    font-family: 'Microsoft YaHei', sans-serif;
                    margin: 0;
                    padding: 15px;
                    background-color: #f0f2f5;
                }

                .container {
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    border-radius: 12px;
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                    padding: 15px;
                }

                .week-info {
                    text-align: center;
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                    margin-bottom: 15px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #eee;
                }

                .course-block {
                    background-color: #f8f9fa;
                    border-radius: 10px;
                    margin-bottom: 12px;
                    overflow: hidden;
                    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
                }

                .time-column {
                    background-color: #4a6fd5;
                    color: white;
                    padding: 10px 15px;
                    font-size: 14px;
                    display: flex;
                    align-items: center;
                }

                .course-details {
                    padding: 10px 15px;
                }

                .course-name {
                    font-size: 15px;
                    font-weight: bold;
                    margin-bottom: 5px;
                    color: #333;
                }

                .course-detail-item {
                    margin-bottom: 3px;
                    font-size: 13px;
                    color: #666;
                }

                .course-type {
                    margin-top: 3px;
                    font-size: 12px;
                    color: #888;
                    font-style: normal;
                }

                @media (min-width: 600px) {
                    .course-block {
                        display: flex;
                    }
                    .time-column {
                        width: 100px;
                    }
                    .course-details {
                        flex-grow: 1;
                    }
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="week-info">第 {{weeks}}周 周{{day}}课程表</div>
                {% for course in courses %}
                    <div class="course-block">
                        <div class="time-column">{{ course.time_slot }}</div>
                        <div class="course-details">
                            <div class="course-name">{{ course.course_name }}</div>
                            <div class="course-detail-item">教师: {{ course.teacher }}</div>
                            <div class="course-detail-item">地点: {{ course.location }}</div>
                            <div class="course-type">类型: {{ course.course_type }}</div>
                        </div>
                    </div>
                {% endfor %}
            </div>
        </body>
        </html>"""
    def to_base64(self, input_str):
        '''
        将字符串转换为base64编码
        :param input_str: 输入字符串
        :return: base64编码字符串
        '''
        bytes_str = input_str.encode('utf-8')
        base64_bytes = base64.b64encode(bytes_str)
        return base64_bytes.decode('utf-8')
    def render_template(self, template_str, data):
        '''
        渲染 HTML 模板
        :param template_str: HTML 模板字符串
        :param data: 渲染数据
        :return: 渲染后的 HTML 字符串
        '''
        env = Environment(loader=BaseLoader())
        template = env.from_string(template_str)
        return template.render(data)
    def _generate_image(self, html_content, output_path):
        # 创建一个临时 HTML 文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
            temp_file.write(html_content.encode("utf-8"))
            temp_file_path = temp_file.name
        service = Service(self.driver_path)
        driver = webdriver.Edge(service=service, options=self.edge_options)
        try:
            # 设置浏览器窗口大小（可根据需要调整）
            driver.set_window_size(800, 700)  # 设置宽度和高度

            # 加载临时 HTML 文件
            driver.get(f"file://{temp_file_path}")
            # 截图并保存
            if os.path.exists(output_path):
                os.remove(output_path)
                logger.info(f"已删除旧图片: {output_path}")
            driver.save_screenshot(output_path)
            logger.info(f"图片已保存到: {output_path}")

        finally:
            # 关闭浏览器
            driver.quit()
            # 删除临时文件
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.error(f"删除临时文件失败: {e}")
    async def get_courses(self):
        '''
        获取课程信息
        :return: 返回课程信息
        '''
        encoded_str = f"{self.to_base64(self.username)}%%%{self.to_base64(self.password)}"
        today = datetime.now().strftime("%Y-%m-%d")

        headers = {
            'Host': 'qzjwpc.cqvtu.edu.cn',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://qzjwpc.cqvtu.edu.cn',
            'Referer': 'https://qzjwpc.cqvtu.edu.cn/jsxsd/xk/LoginToXk',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
        }
        data = {
            'loginMethod': "LoginToXk",
            'userAccount': self.username,
            'userPassword': self.password,
            'encoded': encoded_str,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.LOGIN_URL, headers=headers, data=data) as login_response:
                    await login_response.text()

                timetable_url = self.TIMETABLE_URL_FORMAT.format(date=today)
                async with session.get(timetable_url, headers=headers) as timetable_response:
                    html_content = await timetable_response.text()
                weeks, today_courses, today_reminder = await self.get_daily_timetable(html_content)
                return today_courses, weeks, today_reminder
            except Exception as e:
                logger.error(f"获取课表失败: {e}")
                return "获取课表失败"
    async def get_daily_timetable(self, html_content):
        '''
        获取每日课表
        :param html_content: HTML内容
        :return: 返回周数、今日课程、今日提醒
        '''
        parser = html.HTMLParser()
        root = html.fromstring(html_content, parser=parser)

        color_to_course_type = {
            'rgb(251, 194, 194)': '必修',
            'rgb(205, 221, 252)': '限选',
            'rgb(190, 237, 242)': '任选',
            'rgb(252, 217, 181)': '公选',
            'rgb(247, 247, 248)': '其它'
        }

        time_slot_mapping = {
            "第一二节": "8:30-10:00",
            "第三四节": "10:20-11:50",
            "第五六节": "14:00-15:30",
            "第七八节": "15:50-17:20",
            "第九十节": "18:30-20:00"
        }
        time_slot_mapping_begin = {
            "第一二节": "8:00",
            "第三四节": "9:50",
            "第五六节": "13:30",
            "第七八节": "15:20",
            "第九十节": "18:00"
        }
        timetable = []
        for row in root.xpath('//table[@id="timetable"]/tbody/tr'):
            if not row.xpath('td[1]/text()'):
                continue
            time_slot = row.xpath('td[1]/text()')[0].strip()
            specific_time = time_slot_mapping.get(time_slot, time_slot)
            reminder_time = time_slot_mapping_begin.get(time_slot, time_slot)
            for day_index in range(1, 8):
                course_td = row.xpath(f'td[{day_index + 1}]')
                if not course_td or not course_td[0].text_content().strip():
                    continue
                course_td = course_td[0]

                course_name = course_td.xpath('.//div[@class="item-box"]/p[1]/text()')
                course_name = course_name[0].strip() if course_name else ''
                teacher = course_td.xpath('.//div[@class="tch-name"]/span[1]/text()')
                teacher = teacher[0].strip().replace('教师：', '') if teacher else ''
                location = course_td.xpath('.//div//span[img/@src="/jsxsd/assets_v1/images/item1.png"]/text()')
                location = location[0].strip() if location else ''

                color_span = course_td.xpath('.//span[@class="box"]')
                course_type = ''
                if color_span:
                    style = color_span[0].get('style', '')
                    color_pattern = r'background-color:\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
                    match = re.search(color_pattern, style)
                    if match:
                        rgb_color = f"rgb({match.group(1)}, {match.group(2)}, {match.group(3)})"
                        course_type = color_to_course_type.get(rgb_color, '')

                course_data = {
                    'time_slot': specific_time,
                    'day': day_index,
                    'course_name': course_name,
                    'teacher': teacher,
                    'location': location,
                    'course_type': course_type,
                    'reminder_time': reminder_time,
                    'reminder': f"提醒:\n{specific_time}\n请准备前往 {location},即将开始 {course_name} ({teacher}老师)的课程。"
                }
                timetable.append(course_data)

        start_date = datetime.strptime(self.start_date_str, '%Y-%m-%d')
        now = datetime.strptime(datetime.now().strftime("%Y-%m-%d"), '%Y-%m-%d')
        weeks = (now - start_date).days // 7 + 1
        today = datetime.today().isoweekday()
        today_courses = [course for course in timetable if course['day'] == today]
        today_reminder = [{key: course[key] for key in ['reminder_time', 'reminder']} for course in timetable if
                          course['day'] == today]
        return weeks, today_courses, today_reminder
    async def html_to_image(self, html_content, output_path):
        """将 HTML 内容渲染为图片，使用 Edge 浏览器"""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._generate_image, html_content, output_path)
    async def json_to_markdown(self, course_data):
        '''
        将课程数据转换为Markdown格式
        :param course_data: 课程数据
        :return: Markdown格式的字符串
        '''
        markdown = "|-----------时间段----------|\n|------课程名称------| 教师 |\n|-------地点------| 课程类型 |\n"
        for course in course_data:
            markdown += f"|--------{course['time_slot']}-------|\n| {course['course_name']} | {course['teacher']} |\n|------{course['location']}-----| {course['course_type']} |\n"
        return markdown
    async def generate_schedule_image(self, courses, weeks, output_path):
        """生成课程表 HTML 并渲染为图片"""
        # 构建数据字典
        data = {
            "weeks": weeks,
            "day": self.num_map.get(courses[0]["day"], "未知"),
            "courses": courses
        }
        # 渲染 HTML
        rendered_html = self.render_template(self.TMPL, data)

        # 生成图片
        await self.html_to_image(rendered_html, output_path)

@register("course_query", "CHIYUAN", "查询每日课表", "1.0.2", "https://github.com/yourrepo")
class CourseQueryPlugin(Star):
    def __init__(self, context: Context):
        """
        初始化
        :param context: 上下文
        """
        super().__init__(context)
        self.user = {}  # 使用字典存储用户信息，键为用户ID，值为绑定的User和Password
        self.scheduler = AsyncIOScheduler()  # 创建调度器
        self.course_fetcher = None
        self.message_sender = None

    async def initialize(self):
        """在插件初始化后调用"""
        try:
            # 加载配置
            self.load_config()
            logger.info("配置加载成功")
            # 启动定时任务
            self.start_scheduler()

            logger.info("插件初始化完成")
        except Exception as e:
            logger.error(f"插件初始化失败: {e}")
    def load_config(self):
        """
        加载用户配置
        """
        # 加载 user.ini
        if os.path.exists('user.ini'):
            user_config = configparser.ConfigParser()
            user_config.read('user.ini', encoding='utf-8')
            for user_id in user_config.sections():
                platform = user_config[user_id].get('Platform', '')
                umo = user_config[user_id].get('UMO', '')
                user = user_config[user_id].get('User', '')
                password = user_config[user_id].get('Password', '')
                status = user_config[user_id].get('status', '1')

                if user and password:
                    self.user[user_id] = {
                        'platform': platform,
                        'umo': umo,
                        'user': user,
                        'password': password,
                        'status': status,
                    }
                    logger.info(
                        f"从 user.ini 加载用户: {user_id}, User: {user}, Password: {password}, Platform: {platform}")

    def save_user_config(self):
        """
        保存用户配置
        """
        # 保存 user.ini
        config = configparser.ConfigParser()
        for user_id, info in self.user.items():
            config[user_id] = {
                'Platform': info['platform'],
                'UMO': info['umo'],
                'User': info['user'],
                'Password': info['password'],
                'status': info['status'],
            }
        with open('user.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        logger.info(f"保存了 {len(self.user)} 个用户到 user.ini")

    def start_scheduler(self):
        """
        启动定时任务
        """
        if self.scheduler.running:
            self.scheduler.remove_all_jobs()
        self.scheduler.add_job(
            self.send_daily_course,
            CronTrigger(hour=7, minute=55, second=0),
            id="daily_course_reminder",
            name="每日课程提醒"
        )
        self.scheduler.start()
        logger.info("定时任务已启动")

    def stop_scheduler(self):
        """
        停止定时任务
        """
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("定时任务已停止")

    async def terminate(self):
        """在插件卸载时调用"""
        try:
            self.stop_scheduler()
            # 保存用户配置
            self.save_user_config()

            logger.info("插件已成功卸载")
        except Exception as e:
            logger.error(f"插件卸载失败: {e}")
    async def send_reminder(self, user_id, user_info, job_id, reminder):
        """
        发送提醒
        :param user_id: 用户ID
        :param user_info: 用户信息
        :param job_id: 任务ID
        :param reminder: 提醒内容
        """
        message_chain = MessageChain().message(reminder)
        await self.context.send_message(user_info['umo'], message_chain)
        self.scheduler.remove_job(job_id)
        jobs = self.scheduler.get_jobs()
        logger.info(f"当前调度器内的任务数量：{len(jobs)}")
        for job in jobs:
            logger.info(f"任务ID：{job.id}, 任务名称：{job.name}, 下次运行时间：{job.next_run_time}")
        logger.info(f"向用户 {user_id} 发送提醒: {reminder}成功")

    async def send_daily_course(self):
        """
        发送每日课程
        """
        if not self.user:
            logger.info("没有用户开启课程提醒，跳过发送。")
            return
        logger.info("开始获取今日课程信息")
        try:
            for user_id, user_info in self.user.copy().items():
                if user_info.get("status") == "0":
                    logger.info(f"用户 {user_id} 未开启订阅，跳过发送课程信息。")
                    continue
                try:
                    self.course_fetcher = CourseFetcher(user_info['user'], user_info['password'], "2025-02-17")
                    result, weeks, today_reminder = await self.course_fetcher.get_courses()
                    if result!=[]:
                        logger.info(f"成功获取用户 {user_id} 的课程信息")
                        output_path = 'schedule.png'
                        await self.course_fetcher.generate_schedule_image(result, weeks, output_path)
                        message_chain = MessageChain().file_image(output_path)
                        await self.context.send_message(user_info['umo'], message_chain)
                        for reminder in today_reminder:
                            reminder_time_str = reminder['reminder_time']
                            hour, minute = map(int, reminder_time_str.split(':'))
                            now = datetime.now()
                            current_time = now.time()
                            reminder_time = datetime(now.year, now.month, now.day, hour, minute).time()
                            if reminder_time >= current_time:
                                job_id = f"reminder_{user_id}_{reminder_time_str}"
                                self.scheduler.add_job(
                                    self.send_reminder,
                                    CronTrigger(hour=hour, minute=minute, second=0),
                                    id=job_id,
                                    name=f"课程提醒: {reminder_time_str}",
                                    args=[user_id, user_info, job_id, reminder['reminder']]
                                )
                                logger.info(f"创建定时任务{job_id}成功")
                            else:
                                logger.info(f"提醒时间 {reminder_time_str} 已经过，跳过创建定时任务")
                    else:
                        message_chain = MessageChain().message(f"未获取到{user_id}课程信息")
                        await self.context.send_message(user_info['umo'], message_chain)
                        logger.info(f"未获取到{user_id}课程信息")
                except Exception as e:
                    logger.error(f"发送课表给用户 {user_id} 失败: {e}")
                    self.user[user_id]["status"] = "0"
                    self.save_user_config()
                    message_chain = MessageChain().message(f"获取{user_id}课程信息失败已自动关闭订阅")
                    await self.context.send_message(user_info['umo'], message_chain)
                    logger.info(f"获取{user_id}课程信息失败")
        except Exception as e:
            logger.error(f"获取课程信息失败: {e}")

    @filter.on_decorating_result()
    async def on_decorating_result(self, event: AstrMessageEvent):
        """在发送消息前删除消息链中的 <think> 标签及其内容"""
        result = event.get_result()
        chain = result.chain
        new_chain = []
        think_content = None
        think_pattern = re.compile(r'<think>(.*?)</think>\n', flags=re.DOTALL)
        for item in chain:
            if isinstance(item, Plain):
                # 提取 <think> 标签中的内容
                match = think_pattern.search(item.text)
                if match:
                    think_content = match.group(1).strip()
                    # 清理原始文本，移除 <think> 标签及其内容
                    cleaned_text = think_pattern.sub('', item.text)
                    new_chain.append(Plain(cleaned_text))
                else:
                    new_chain.append(item)
            else:
                new_chain.append(item)
        if think_content:
            logger.info("思考内容:\n" + think_content + "\n")
        result.chain = new_chain

    @filter.command("课程")
    async def query_course(self, event: AstrMessageEvent):
        """
        查询课程
        :param event: 事件
        """
        logger.info("查询课表指令触发")
        user_id = event.get_sender_id()
        if user_id not in self.user:
            logger.warning(f"用户 {user_id} 未在 user.ini 中注册")
            yield event.plain_result("您尚未注册订阅，请先执行 /注册订阅 命令。")
            return
        user_info = self.user[user_id]
        self.course_fetcher = CourseFetcher(user_info['user'], user_info['password'], "2025-02-17")
        result, weeks, today_reminder = await self.course_fetcher.get_courses()
        result = await self.course_fetcher.json_to_markdown(result)
        yield event.plain_result(result)

    @filter.command("注册订阅")
    async def enable_reminder(self, event: AstrMessageEvent, user: str, password: str):
        """
        开启提醒
        :param event: 事件
        :param user: 用户名
        :param password: 密码
        """
        user_id = event.get_sender_id()
        umo = event.unified_msg_origin
        logger.info(f"接收到开启提醒指令，用户ID: {user_id}")
        # 根据事件来源设置平台
        if event.get_platform_name() == "aiocqhttp":
            platform = "QQ"
        elif event.get_platform_name() == "wechatpadpro":
            platform = "微信"
        elif event.get_platform_name() == "lark":
            platform = "飞书"
        else:
            platform = "未知"
        if user_id not in self.user:
            self.user[user_id] = {
                'platform': platform,
                'umo': umo,
                'user': user,
                'password': password,
                "status" : "1",
            }
            self.save_user_config()
            logger.info(f"新增开启提醒的用户: {user_id}, User: {user}, Password: {password}, Platform: {platform}")
            message_chain = MessageChain().message("已注册每日课程提醒！")
            await self.context.send_message(self.user[user_id]['umo'], message_chain)
        else:
            del self.user[user_id]
            self.save_user_config()
            logger.info(f"删除并重建用户: {user_id}")
            # 重新创建用户信息
            self.user[user_id] = {
                'platform': platform,
                'umo': umo,
                'user': user,
                'password': password,
                "status": "1",
            }
            self.save_user_config()
            logger.info(
                f"重建后新增开启提醒的用户: {user_id}, User: {user}, Password: {password}, Platform: {platform}")
            yield event.plain_result("已重建用户信息。")

    @filter.command("注销订阅")
    async def disable_reminder(self, event: AstrMessageEvent):
        """
        关闭提醒
        :param event: 事件
        """
        user_id = event.get_sender_id()
        logger.info(f"接收到关闭提醒指令，用户ID: {user_id}")

        if user_id in self.user:
            del self.user[user_id]
            self.save_user_config()
            logger.info(f"移除开启提醒的用户: {user_id}")
            yield event.plain_result("已注销每日课程提醒！")
        else:
            logger.info(f"用户不存在，无需关闭: {user_id}")
            yield event.plain_result("每日课程提醒未注册，无需关闭。")

    @filter.command("start")
    async def start_reminder(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.user:
            yield event.plain_result("未注册用户")
        else:
            self.user[user_id]["status"] = "1"
            self.save_user_config()
            yield event.plain_result("已开启")
    @filter.command("off")
    async def off_reminder(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.user:
            yield event.plain_result("未注册用户")
        else:
            self.user[user_id]["status"] = "0"
            self.save_user_config()
            yield event.plain_result("已关闭")
    @filter.command("开启定时")
    async def start_scheduler_cmd(self, event: AstrMessageEvent):
        """
        开启定时任务
        :param event: 事件
        """
        if not self.scheduler.get_job('daily_course_reminder'):
            self.start_scheduler()
        yield event.plain_result("定时任务已启动")

    @filter.command("关闭定时")
    async def stop_scheduler_cmd(self, event: AstrMessageEvent):
        """
        关闭定时任务
        :param event: 事件
        """
        self.stop_scheduler()
        yield event.plain_result("定时任务已停止")

    @filter.command("course")
    async def query_courses(self, event: AstrMessageEvent):
        """
        查询课程
        :param event: 事件
        """
        logger.info("查询课表指令触发")
        user_id = event.get_sender_id()
        if user_id not in self.user:
            logger.warning(f"用户 {user_id} 未在 user.ini 中注册")
            yield event.plain_result("您尚未注册订阅，请先执行 /注册订阅 命令。")
            return
        user_info = self.user[user_id]
        self.course_fetcher = CourseFetcher(user_info['user'], user_info['password'], "2025-02-17")
        result, weeks, today_reminder = await self.course_fetcher.get_courses()
        if result == []:
            yield event.plain_result("未获取到课程信息")
        else:
            output_path = 'schedule.png'
            await self.course_fetcher.generate_schedule_image(result, weeks, "schedule.png")
            yield event.image_result(output_path)

    @filter.command("查看任务")
    async def look(self, event: AstrMessageEvent):
        jobs = self.scheduler.get_jobs()
        logger.info(f"当前调度器内的任务数量：{len(jobs)}")
        result=""
        for job in jobs:
            result += f"任务ID：{job.id}\n"
            logger.info(f"任务ID：{job.id}, 任务名称：{job.name}, 下次运行时间：{job.next_run_time}")
        yield event.plain_result(result)

    @filter.command("ce")
    async def ce(self,event: AstrMessageEvent):
        await self.send_daily_course()

    @filter.command("帮助")
    async def help(self, event: AstrMessageEvent):
        """
        显示帮助信息
        :param event: 事件
        """
        yield event.image_result("帮助.jpg")

    @filter.command("反馈")
    async def feedback(self, event: AstrMessageEvent, arg: str ):
        """处理用户反馈"""
        user_id = event.get_sender_id()
        feedback_content = arg
        # 在这里可以添加将反馈内容保存到文件、数据库或其他处理逻辑
        try:
            # 示例：将反馈内容保存到文件
            with open("feedback.txt", "a", encoding="utf-8") as f:
                f.write(f"User: {user_id}\nFeedback: {feedback_content}\n{'-' * 50}\n")
            logger.info(f"Received feedback from user {user_id}: {feedback_content}")
            yield event.plain_result("不怎么感谢您的反馈！我不会认真考虑您的建议。")
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}")
            yield event.plain_result("反馈提交失败，请稍后再试！")

    @filter.command("赞助")
    async def zanzhu(self, event: AstrMessageEvent):
        yield event.image_result("赞助.jpg")
