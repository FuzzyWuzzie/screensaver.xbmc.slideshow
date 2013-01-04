# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with XBMC; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html

# TODO conditional exif rotation
# TODO conditional zoom based on slideshow time

import os, sys, random, urllib
import xbmc, xbmcgui, xbmcaddon, xbmcvfs
from xml.dom.minidom import parse
from PIL import Image
if sys.version_info < (2, 7):
    import simplejson
else:
    import json as simplejson

__addon__    = sys.modules[ "__main__" ].__addon__
__addonid__  = sys.modules[ "__main__" ].__addonid__
__cwd__      = sys.modules[ "__main__" ].__cwd__
__skindir__  = xbmc.getSkinDir().decode("utf-8")
__skinhome__ = xbmc.translatePath( os.path.join( 'special://home/addons/', __skindir__, 'addon.xml' ).encode("utf-8") ).decode("utf-8")
__skinxbmc__ = xbmc.translatePath( os.path.join( 'special://xbmc/addons/', __skindir__, 'addon.xml' ).encode("utf-8") ).decode("utf-8")

IMAGE_TYPES = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.ico', '.tif', '.tiff', '.tga', '.pcx')

EFFECTLIST = ["('effect=slide start=0,0 end=0,0 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=400 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=1280,0 end=-1280,0 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=-1280,0 end=1280,0 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=0,720 end=0,-720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=0,-720 end=0,720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=1280,720 end=-1280,-720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=-1280,720 end=1280,-720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=1280,-720 end=-1280,720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')",
             "('effect=slide start=-1280,-720 end=1280,720 time=%i condition=true', 'conditional'), ('effect=zoom start=100 end=100 center=auto time=%i condition=true', 'conditional')"]

def log(txt):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (__addonid__, txt)
    xbmc.log(msg=message.encode("utf-8"), level=xbmc.LOGDEBUG)

class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__( self, *args, **kwargs ):
        pass

    def onInit(self):
        # load constants
        self._get_conts()
        self._get_settings()
        # get the effectslowdown value from the current skin
        effectslowdown = self._get_animspeed()
        # use default if we couldn't find the effectslowdown value
        if not effectslowdown:
            effectslowdown = 1
        # calculate the animation time
        speedup = 1 / float(effectslowdown)
        self.adj_time = int(101000 * speedup)
        # get the images
        items = self._get_items()
        if items:
            # hide startup splash
            self._set_prop('Splash', 'hide')
            # start slideshow
            self._start_show(items)

    def _get_conts(self):
        self.winid   = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
        self.Monitor = MyMonitor(action = self._exit)
        self.stop    = False
        self.startup = True

    def _get_settings(self):
        self.slideshow_type   = __addon__.getSetting('type')
        self.slideshow_path   = __addon__.getSetting('path')
        self.slideshow_effect = __addon__.getSetting('effect')
        self.slideshow_time   = int(__addon__.getSetting('time'))
        self.slideshow_dim    = hex(int('%.0f' % (float(__addon__.getSetting('level')) * 2.55)))[2:] + 'ffffff' # convert float to hex value usable by the skin
        self.slideshow_scale  = __addon__.getSetting('scale')
        # select which image controls from the xml we are going to use
        if self.slideshow_scale == 'false':
            self.image1 = self.getControl(1)
            self.image2 = self.getControl(2)
            self.getControl(1).setVisible(False)
            self.getControl(2).setVisible(False)
            self.getControl(3).setVisible(False)
            self.getControl(4).setVisible(False)
        else:
            self.image1 = self.getControl(3)
            self.image2 = self.getControl(4)
            self.getControl(1).setVisible(False)
            self.getControl(2).setVisible(False)
            self.getControl(3).setVisible(False)
            self.getControl(4).setVisible(False)
        self.slideshow_name = __addon__.getSetting('label')
        if self.slideshow_name == '0':
            self.getControl(99).setVisible(False)
        else:
            self.namelabel = self.getControl(99)
        # add 1 sec fadeout time to showtime
        self.anim_time = self.slideshow_time + 1
        # set the dim property
        self._set_prop('Dim', self.slideshow_dim)

    def _set_prop(self, name, value):
        self.winid.setProperty('SlideView.%s' % name, value)

    def _clear_prop(self, name):
        self.winid.clearProperty('SlideView.%s' % name)

    def _get_animspeed(self):
        # find the skindir
        if xbmcvfs.exists( __skinxbmc__ ):
            # xbmc addon dir
            skinxml = __skinxbmc__
        elif xbmcvfs.exists( __skinhome__ ):
            # user addon dir
            skinxml = __skinhome__
        else:
            return
        try:
            # parse the skin addon.xml
            self.xml = parse(skinxml)
            # find all extension tags
            tags = self.xml.documentElement.getElementsByTagName( 'extension' )
            for tag in tags:
                # find the effectslowdown attribute
                for (name, value) in tag.attributes.items():
                    if name == 'effectslowdown':
                        anim = value
                        return anim
        except:
            return

    def _get_items(self):
	# image folder (fallback to video fanart if path is empty)
        if self.slideshow_type == "2":
            if not self.slideshow_path:
                self.slideshow_type = "0"
	# video fanart
        if self.slideshow_type == "0":
            methods = [('VideoLibrary.GetMovies', 'movies'), ('VideoLibrary.GetTVShows', 'tvshows')]
	# music fanart
        elif self.slideshow_type == "1":
            methods = [('AudioLibrary.GetArtists', 'artists')]
        # picture source
        if self.slideshow_type == "2":
            items = self._walk(self.slideshow_path)
        else:
            items = []
            for method in methods:
                json_query = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "' + method[0] + '", "params": {"properties": ["fanart"]}, "id": 1}')
                json_query = unicode(json_query, 'utf-8', errors='ignore')
                json_response = simplejson.loads(json_query)
                if json_response.has_key('result') and json_response['result'] != None and json_response['result'].has_key(method[1]):
                    for item in json_response['result'][method[1]]:
                        if item['fanart']:
                            items.append(item['fanart'])
        # randomize
        random.shuffle(items, random.random)
        return items

    def _start_show(self, items):
        # start with image 1
        cur_img = self.image1
        order = [1,2]
        # loop until onScreensaverDeactivated is called
        while (not xbmc.abortRequested) and (not self.stop):
            # iterate through all the images
            for img in items:
                # add image to gui
                cur_img.setImage(img)
                # give xbmc some time to load the image
                if not self.startup:
                    xbmc.sleep(1000)
                self.startup = False
                # get the file or foldername if enabled in settings
                if self.slideshow_name != '0':
                    if self.slideshow_name == '1':
                        NAME, EXT = os.path.splitext(os.path.basename(img))
                    elif self.slideshow_name == '2':
                        ROOT, NAME = os.path.split(os.path.dirname(img))
                    self.namelabel.setLabel(NAME)
                # set animations
                if self.slideshow_effect == "0":
                    # add slide anim
                    self._set_prop('Slide%d' % order[0], '0')
                    self._set_prop('Slide%d' % order[1], '1')
                else:
                    # add random slide/zoom anim
                    if self.slideshow_effect == "2":
                        tex_width = 1280.0
                        tex_height = 720.0
                        xoff = 0
                        yoff = 0
# WIP
                        # if the anim time is greater the 50 seconds, the image might be offscreen
                        if __addon__.getSetting('scale') == 'false' and ((self.anim_time) > 50):
                            # get image size
                            size = self._getsize(img)
                            if size:
                                width  = float(size[0])
                                height = float(size[1])
                                # recalculate real image size to screensize
                                aspect = width / height
                                if aspect < (16.0/9.0):
                                    # portrait
                                    factor = height / 720.0
                                    tex_width = width / factor
                                    # calculate the amount of pix of the image on the screen
                                    xinside = 1280.0 - (12.8 * float(self.anim_time))
                                    # calculate the x offset
                                    if (1280.0 - (2.0 * xinside)) > tex_width:
                                       xoff = ((1280.0 - (2.0 * xinside)) - tex_width) / 2.0
                                elif aspect > (16.0/9.0):
                                    # landscape
                                    factor = width / 1280.0
                                    tex_height = height / factor
                                    # calculate the amount of pix of the image on the screen
                                    yinside = 720.0 - (7.2 * float(self.anim_time))
                                    # calculate the y offset
                                    if (720.0 - (2.0 * yinside)) > tex_height:
                                       yoff = ((720.0 - (2.0 * yinside)) - tex_heigth) / 2.0
# /WIP
                        # add random slide/zoom anim
                        self._anim(cur_img, xoff, yoff)
                    # add fade anim, used for both fade and slide/zoom anim
                    self._set_prop('Fade%d' % order[0], '0')
                    self._set_prop('Fade%d' % order[1], '1')
                # show the image
                cur_img.setVisible(True)
                # define next image
                if cur_img == self.image1:
                    cur_img = self.image2
                    order = [2,1]
                else:
                    cur_img = self.image1
                    order = [1,2]
                # slideshow time in secs (we already slept for 1 second)
                count = self.slideshow_time - 1
                # display the image for the specified amount of time
                while (not xbmc.abortRequested) and (not self.stop) and count > 0:
                    count -= 1
                    xbmc.sleep(1000)
                # break out of the for loop if onScreensaverDeactivated is called
                if  self.stop or xbmc.abortRequested:
                    break
                # set visible to false for the next image
                cur_img.setVisible(False)

    def _walk(self, path):
        images = []
        folders = []
        # multipath support
        if path.startswith('multipath://'):
            # get all paths from the multipath
            paths = path[12:-1].split('/')
            for item in paths:
                folders.append(urllib.unquote_plus(item))
        else:
            folders.append(path)
        for folder in folders:
            if xbmcvfs.exists(xbmc.translatePath(folder)):
                # get all files and subfolders
                dirs,files = xbmcvfs.listdir(folder)
                for item in files:
                    # filter out all images
                    if os.path.splitext(item)[1].lower() in IMAGE_TYPES:
                        images.append(os.path.join(folder,item))
                for item in dirs:
                    # recursively scan all subfolders
                    images += self._walk(os.path.join(folder,item))
        return images

    def _anim(self, cur_img, xoff, yoff):
        # reset position the current image
        cur_img.setPosition(0, 0)
        # pick a random anim
        number = random.randint(0,8)
        posx = 0
        posy = 0
# WIP
        adj_time = float(self.adj_time)
        # calculate anim time:
        if xoff != 0:
            adj_time = int(((2560.0 / (2560.0 - (2.0 * xoff))) * adj_time) + 0.5)
        elif yoff != 0:
            adj_time = int(((1440.0 / (1440.0 - (2.0 * xoff))) * adj_time) + 0.5)
# /WIP
        # calculate posx and posy offset depending on the selected time per image
        if number == 1 or number == 5 or number == 7:
            posx = int(-1280 + (12.8 * self.anim_time) - xoff + 0.5)
        elif number == 2 or number == 6 or number == 8:
            posx = int(1280 - (12.8 * self.anim_time) + xoff + 0.5)
        if number == 3 or number == 5 or number == 6:
            posy = int(-720 + (7.2 * self.anim_time) - yoff + 0.5)
        elif number == 4 or number == 7 or number == 8:
            posy = int(720 - (7.2 * self.anim_time) + yoff + 0.5)
        # position the current image
        cur_img.setPosition(posx, posy)
        # add the animation to the current image
        cur_img.setAnimations(eval(EFFECTLIST[number] % (adj_time,adj_time)))

    def _getsize(self, image):
        try:
            img = Image.open(image)
            size = img.size
            return size
        except:
            return

    def _exit(self):
        # exit when onScreensaverDeactivated gets called
        self.stop = True
        # clear our properties on exit
        self._clear_prop('Slide1')
        self._clear_prop('Slide2')
        self._clear_prop('Fade1')
        self._clear_prop('Fade2')
        self._clear_prop('Dim')
        self._clear_prop('Splash')
        self.close()

# TODO exif rotation
#    def get_exif(fn):
#        from PIL.ExifTags import TAGS
#        ret = {}
#        i = Image.open(fn)
#        info = i._getexif()
#        for tag, value in info.items():
#            decoded = TAGS.get(tag, tag)
#            ret[decoded] = value
#        return ret

class MyMonitor(xbmc.Monitor):
    def __init__( self, *args, **kwargs ):
        self.action = kwargs['action']

    def onScreensaverDeactivated(self):
        self.action()
