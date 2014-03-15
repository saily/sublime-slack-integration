import sublime
import sublime_plugin
import threading

from .api import api_call


API_CHANNELS = 'https://slack.com/api/channels.list'
API_USERS = 'https://slack.com/api/users.list'
API_GROUPS = 'https://slack.com/api/groups.list'
API_POST_MESSAGE = 'https://slack.com/api/chat.postMessage'


class BaseSend(sublime_plugin.TextCommand):
    """ Base class which shows a channels list and sends messages """

    def __init__(self, view):
        super(BaseSend, self).__init__(view)
        # here we will store all messages
        self.messages = []

        # this channels list is only populated once, per sublime session
        # you need to restart sublime to re-take channels from API
        self.receivers = []

        # load plugin settings
        self.settings = sublime.load_settings("Slack.sublime-settings")

    def run(self, view):
        # reset older messages stored in memory
        self.messages = []
        # check if token is set
        if not self.settings.get('team_tokens'):
            sublime.error_message('SLACK: Error! Please set your API "token" in Preferences -> Package Settings -> Slack -> Settings - User')
            raise Exception('Team Token missing')

    def on_select_receiver(self, index):
        if index is -1:
            print(index, self)
            return sublime.status_message('SLACK: sending cancelled')

        receiver = self.receivers[index]
        sublime.status_message("Sending selection to: " + receiver.get('name'))

        username = self.settings.get('username')
        info = sublime.platform()
        try:
            import getpass
            info = "{0}, {1}".format(getpass.getuser(), info)
        except:
            # cannot get current OS user
            pass

        for message in self.messages:
            args = {
                'token': receiver.get('token'),
                'channel': receiver.get('id'),
                'text': message,
                'username': "{0} ({1})".format(username, info)
            }
            response = api_call(API_POST_MESSAGE, args)
            if response['ok']:
                sublime.status_message('SLACK: Message sent successfully!')
            else:
                sublime.status_message('SLACK: Unexpected error!')

    def init_message_send(self):
        print("init")
        # check is channels are cached in memory
        receivers = []
        if not self.receivers:
            # get the channels and users for each team
            sublime.status_message('Loading channels/users ... Please wait ...')
            for team, token in self.settings.get('team_tokens').items():
                channels_response = api_call(API_CHANNELS, {
                    'token': token,
                    'exclude_archived': 1
                })
                for channel in channels_response['channels']:
                    # bind the token and team to the channel
                    channel['token'] = token
                    channel['team'] = team
                    channel['type'] = 'channel'
                    self.receivers.append(channel)

                groups_response = api_call(API_GROUPS, {
                    'token': token,
                    'exclude_archived': 1
                })
                for group in groups_response['groups']:
                    # bind the token and team to the group
                    group['token'] = token
                    group['team'] = team
                    group['type'] = 'group'
                    self.receivers.append(group)

                users_response = api_call(API_USERS, {
                    'token': token
                })
                for user in users_response['members']:
                    if not user['deleted']:
                        # bind the token and team to the user
                        user['token'] = token
                        user['team'] = team
                        user['type'] = 'user'
                        self.receivers.append(user)
            # loading done, remove status message
            sublime.status_message('')

        # create receivers dropdown
        for receiver in self.receivers:
            if receiver['type'] is 'channel':
                item = "# {0}".format(receiver['name'])
            elif receiver['type'] is 'group':
                item = "● {0}".format(receiver['name'])
            else:  # is user
                item = "@ {0}".format(receiver['name'])
            if len(self.settings.get('team_tokens')) > 1:
                item += "({0})".format(team)
            receivers.append(item)

        # display a popup and let the user pick a channel
        self.view.window().show_quick_panel(
            receivers,
            self.on_select_receiver)


class SendSelectionCommand(BaseSend):
    """ Send the selected text to slack. Multiple selections supported """
    def run(self, view):
        super(SendSelectionCommand, self).run(view)
        # get all selected regions
        for region in self.view.sel():
            text = self.view.substr(region)

            if not text:
                sublime.error_message("SLACK: Error! No text selected")
                return
            self.messages.append(text)

        threading.Thread(target=self.init_message_send).start()


class SendMessageCommand(BaseSend):
    """ Send a message from user input """

    def run(self, view):
        super(SendMessageCommand, self).run(view)
        self.view.window().show_input_panel(
            "Enter a message", '', self.on_done, None, None)

    def on_done(self, message):
        if not message:
            return sublime.error_message('ERROR: Please enter a message')
        self.messages = [message]
        threading.Thread(target=self.init_message_send).start()
