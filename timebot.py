#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import datetime as dt
import time
import string
import vk
import sys
import re
from pymongo import MongoClient

import parser
import consts as CONST
import logger as lg
import security


# Class implement bot logic. The main idea of this bot to help everyone with schedule.
# Bot intergated to socialnet and like a friend can tell you what next lection you will have.
# Normal documentation will be in future.
class Timebot:
	def __init__(self):
		self.db = MongoClient().timebot
		self.logger = lg.Logger()
		self.msg_stack = []


	def getLessonNumb(self, dt_time):
		return {
								dt_time < dt.time(9,0,0): 0,
			dt.time(9,0,0) 	 <= dt_time < dt.time(10,45,0): 1,
			dt.time(10,45,0) <= dt_time < dt.time(12,50,0): 2,
			dt.time(12,50,0) <= dt_time < dt.time(14,35,0): 3,
			dt.time(14,35,0) <= dt_time < dt.time(16,20,0): 4,
			dt.time(16,20,0) <= dt_time < dt.time(18,0,0):  5,
			dt.time(18,0,0)  <= dt_time < dt.time(21,20,0): 6,
			dt.time(21,20,0) <= dt_time: 7
		}[True]

	def isThatWeek(self, native_week, base_week):
		base_week = base_week - dt.date(2016, 9, 1).isocalendar()[1] + 1
	
		if native_week == '':
			result = True
		elif 'I' in native_week:
			result = (base_week % 2 == 0) == (native_week.strip() == 'II')
		elif '-' in native_week:
			period = re.split('-', native_week)
			result = (base_week >= int(period[0])) and (base_week <= int(period[1]))
		else:
			result = str(base_week) in re.split(r'[\s,]', native_week)
		return result

	def getLessons(self, group, day, week, lstart = 1, lfinish = 6):
		try:
			schedule = self.db.schedule.find({'group':group})[0]['schedule']
		except:
			raise Exception(CONST.ERR_GROUP_NOT_FOUND)
		
		lessons = ''
		for lesson in schedule:
			if (lesson['day'] == day) \
			and (self.isThatWeek(lesson['week'], week))\
			and (lesson['numb'] >= lstart)\
			and (lesson['numb'] <= lfinish):
				lessons += CONST.UNI_TEMPLATE.format(
					lesson['numb'],
					lesson['room'], 
					CONST.LECTION_TIME[lesson['numb']],
					lesson['name']				
				)

		if lessons == '':
			raise Exception(CONST.ERR_NO_LECTIONS)

		return lessons


	def cmdUniversal(self, params):	
		if params['lesson']:
			lesson = params['lesson']
			les = self.getLessons(params['group'], params['day'], params['week'], lesson, lesson)
		else:
			les = self.getLessons(params['group'], params['day'], params['week'])
		return les

	def cmdNext(self, params):
		lection_start = int(self.getLessonNumb(dt.datetime.now().time())) + 1
		return  self.getLessons(params['group'], params['day'], params['week'], lection_start)

	def cmdWeek(self, params):
		week = params['week'] - dt.date(2016, 9, 1).isocalendar()[1] + 1
		
		return CONST.USER_MESSAGE[CONST.CMD_WEEK].format(week)

	def cmdNow(self, params):
		lection = int(self.getLessonNumb(dt.datetime.now().time()))
	
		return  self.getLessons(params['group'], params['day'], params['week'], lection, lection)

	def cmdLectionsTime(self, params):
		msg = ''
		for i in CONST.LECTION_TIME:
			msg += CONST.USER_MESSAGE[CONST.CMD_LECTIONS_TIME].format(i, CONST.LECTION_TIME[i])

		return msg

	def cmdTeacher(self, params):
		day	 = params['day']
		week = params['week']
		numb = params['lesson']

		try:
			schedule = self.db.schedule.find({'group':params['group']})[0]['schedule']
		except:
			raise Exception(CONST.ERR_GROUP_NOT_FOUND)
		
		teacher = ''
		for lesson in schedule:
			if (lesson['day'] == day) \
			and (self.isThatWeek(lesson['week'], week))\
			and (lesson['numb'] == numb):
				teacher = lesson['teacher']
				if not teacher:
					raise Exception(CONST.ERR_NO_TEACHER)

		if not teacher:
			raise Exception(CONST.ERR_NO_LECTIONS)
		
		return teacher

	def cmdHelp(self, params):
		return ''

	def cmdPolite(self, params):
		return ''
	
	def cmdFindLection(self, params):
		raise Exception(CONST.ERR_SKIP)
		return ''

	def cmdFindTeacher(self, params):
		raise Exception(CONST.ERR_SKIP)
		return ''

	def cmdWhenExams(self, params):
		week = params['week'] - dt.date(2016, 9, 1).isocalendar()[1] + 1
		
		now = dt.datetime.now().date()
		start = dt.date(2016, 9, 1)
		end = dt.date(2016, 12, 22)
		delta = end - now
		weeks = delta.days / 7
		days  = delta.days % 7

		delta = now - start
		amount = end - start
		percent = str(delta.days % amount.days) + '%'

		return CONST.USER_MESSAGE[CONST.CMD_WHEN_EXAMS].format(weeks, days, percent)


	functions = {
		CONST.CMD_UNIVERSAL			: cmdUniversal,
		CONST.CMD_NEXT 				: cmdNext,
		CONST.CMD_TODAY 			: cmdUniversal,
		CONST.CMD_AFTERTOMMOROW 	: cmdUniversal,
		CONST.CMD_TOMMOROW			: cmdUniversal,
		CONST.CMD_YESTERDAY			: cmdUniversal,
		CONST.CMD_DAY_OF_WEEK 		: cmdUniversal,
		CONST.CMD_WEEK				: cmdWeek,
		CONST.CMD_NOW				: cmdNow,
		CONST.CMD_BY_DATE			: cmdUniversal,
		CONST.CMD_BY_TIME			: cmdUniversal,
		CONST.CMD_LECTION_NUMB		: cmdUniversal,
		CONST.CMD_HELP				: cmdHelp,
		CONST.CMD_POLITE			: cmdPolite,
		CONST.CMD_LECTIONS_TIME		: cmdLectionsTime,
		CONST.CMD_TEACHER			: cmdTeacher,
		CONST.CMD_FIND_LECTION		: cmdFindLection,
		CONST.CMD_WHEN_EXAMS		: cmdWhenExams
	}

	
	def findKeywords(self, words, text):
		keyword = {}
		for idx, word in enumerate(words):
			try:
				result = re.search(word, text).group()
			except:
				continue
			if result:
				keyword = {'idx': idx, 'word': result}
				break
		return keyword

	def retriveBody(self, message):
		msg = message.copy()
		go_deeper = True
		while go_deeper:
			if self.is_exist(msg, 'fwd_messages'):
				msg = msg['fwd_messages'][0]
			else:
				go_deeper = False

		return msg['body']

	def getGroup(self, message, text, is_chat):
		answer 		= ''
		found_group = ''
		vk_id 		= message['chat_id' if is_chat else 'uid']
		try:
			found_group = self.db.users.find({'vk_id':vk_id, 'chat': is_chat})[0]['group_name']
		except:	
			pass

		match = re.search(u'[а-я]{4}[а-я]?-[0-9]{2}-[0-9]{2}', text)
		group = match.group(0) if match else ''

		if group and found_group:
			self.db.users.update_one(
				{'vk_id':vk_id, 'chat': is_chat},
				{'$set': {'group_name': group}}
			)
			answer += CONST.USER_PREMESSAGE[CONST.SAVED_GROUP].format(group)
		elif group:
			self.db.users.insert_one({
				'vk_id': vk_id, 
				'chat': is_chat, 
				'group_name': group
			})
			answer += CONST.USER_PREMESSAGE[CONST.SAVED_GROUP].format(group)
			answer += CONST.USER_PREMESSAGE[CONST.CMD_HELP]
		elif found_group:
			group = found_group
		else:
			raise Exception(CONST.ERR_NO_GROUP)	

		return group, answer	

	# Takes message and prepare answer for it.
	# Return type: string
	def getMyAnswer(self, message, is_chat):
		answer 		= ''
		answer_ok	= False
		text 		= self.retriveBody(message)
		text 		= text.lower()

		if is_chat and not any(re.match('^'+word, text) for word in CONST.CHAT_KEYWORDS):
			raise Exception(CONST.ERR_SKIP)
		text = ' ' + text # TODO Very bad, need to fix

		if self.findKeywords(CONST.CMD_KEYWORDS[CONST.CMD_FEEDBACK], text):
			try:
				user_id = str(message['uid'])
			except:
				user_id = ''
			self.logger.log(CONST.LOG_FBACK, user_id + ' ' + text)
			answer = CONST.USER_PREMESSAGE[CONST.CMD_FEEDBACK]
			return answer

		group, answer 	= self.getGroup(message, text, is_chat)
		markers 		= {}
		base_cmd		= {'cmd': CONST.CMD_UNIVERSAL}
		date 			= dt.datetime.today()
		lesson 			= 0

		answer_ok = bool(answer)

		for cmd, keywords in CONST.CMD_KEYWORDS.items():
			word = self.findKeywords(keywords, text) 
			if word and cmd in CONST.MARKERS:
				markers[cmd] = word
			elif word:	
				base_cmd['cmd'] 	= cmd 
				base_cmd['keyword'] = word
				answer_ok 			= True

		for command, keyword in markers.items():
			if command == CONST.CMD_TOMMOROW:
				date = dt.datetime.today() + dt.timedelta(days=1)
			elif command == CONST.CMD_AFTERTOMMOROW:
				date = dt.datetime.today() + dt.timedelta(days=2)
			elif command == CONST.CMD_YESTERDAY:
				date = dt.datetime.today() - dt.timedelta(days=1)
			elif command == CONST.CMD_DAY_OF_WEEK:
				for i in range(0,7):
					temp_date = dt.datetime.today() + dt.timedelta(days=i)
					if temp_date.weekday() == keyword['idx']:
						date = temp_date
						break
			elif command == CONST.CMD_LECTION_NUMB:
				lesson = keyword['idx']
				keyword['word'] = keyword['idx']
			elif command == CONST.CMD_BY_TIME:
				try:
					lesson = self.getLessonNumb(dt.datetime.strptime(keyword['word'], '%H:%M').time())
				except:
					del markers[command]
			elif command == CONST.CMD_BY_DATE:
				try:
					# TODO Fix wrong code below
					date = dt.datetime.strptime(keyword['word']+'.2016', '%d.%m.%Y').date()
				except:
					try:
						day, month = keyword['word'].split(' ')
						mnumb = 0
						for idx, name in enumerate(CONST.MONTH_NAMES):
							if re.search(name, month):
								mnumb = idx + 1
								break
						date = dt.date(2016, mnumb, int(day))
					except:
						del markers[command]

		params = {
			'group'	: group,
			'day' 	: date.weekday(),
			'week'	: date.isocalendar()[1],
			'lesson': lesson
		}

		header = ''
		for cmd, kwd in markers.items():
			header += CONST.USER_PREMESSAGE[cmd].format(kwd['word'])
			answer_ok = True
		if not answer_ok:
			self.logger.log(CONST.LOG_MESGS, text)
			raise Exception(CONST.ERR_SKIP)

		if not header and base_cmd['cmd'] == CONST.CMD_UNIVERSAL:
			base_cmd['cmd'] = CONST.CMD_TODAY
		answer += CONST.USER_PREMESSAGE[base_cmd['cmd']].format(markers = header)
		try:
			answer += self.functions[base_cmd['cmd']](self, params)
		except:
			answer += CONST.ERR_MESSAGES[CONST.ERR_NO_LECTIONS]
		
		return answer		
			

	# Open vkAPI session
	# Return type: vk.api object
	def openVkAPI(self):
		success = False
		while not success:
			try:
				self.logger.log(CONST.LOG_WLOAD, 'Try to open new session.')
				session = vk.AuthSession(
					app_id = security.app_id, 
					user_login = security.user_login, 
					user_password = security.user_password, 
					scope = security.scope)
				api = vk.API(session)
				success = True
				self.logger.log(CONST.LOG_WLOAD, 'New session opened.')
			except Exception as e:
				self.logger.log(CONST.LOG_WLOAD, 'New session not opened!')
				self.logger.log(CONST.LOG_ERROR, e)
				time.sleep(3)
		return api

	# Check element of tuple by index for existance
	# Return type: boolean
	def is_exist(self, tupl, index_name):
		try:
			tmp = tupl[index_name]
			result =  True
		except:
			result = False
		return result

	# Send answer for enter message
	# Return type: string 
	def sendMyAnswer(self, message):
		try:
			answer = ''
			is_chat = self.is_exist(message, 'chat_id')
			try:
				answer  = self.getMyAnswer(message, is_chat)
			except Exception, e:
				if isinstance(e.args[0], int):
					answer = CONST.ERR_MESSAGES[e.args[0]]
				else:
					self.logger.log(CONST.LOG_ERROR, e)
					return
			if answer: 
				fullmsg = str(message['chat_id' if is_chat else 'uid']) + answer 
				if not fullmsg in self.msg_stack:
					if is_chat:
						self.api.messages.send(chat_id=message['chat_id'], message=answer)
					else:
						self.api.messages.send(user_id=message['uid'], message=answer)
					time.sleep(1)
					
					self.msg_stack.append(fullmsg)
					if len(self.msg_stack) > CONST.STACK_LEN:
						self.msg_stack.pop(0)
		except Exception, e:
			self.logger.log(CONST.LOG_WLOAD, 'Message not send!')
			self.logger.log(CONST.LOG_ERROR, e)
			self.api = self.openVkAPI()

	# Scan enter messages and answer
	def run(self):		
		self.api = self.openVkAPI()
		while 1:
			time.sleep(1)
			try:
				new_messages = self.api.messages.get(out=0, count=5, time_offset=15)	
				del new_messages[0]
				for message in new_messages:
					if message['read_state'] == 0:
						self.sendMyAnswer(message)
			except Exception, e:
				self.logger.log(CONST.LOG_ERROR, e)
				self.api = self.openVkAPI()


bot = Timebot()
bot.run()
