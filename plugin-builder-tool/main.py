from printer import *
try:
    # Python 2.7
    from Tkinter import *
    import ttk
    import tkMessageBox
    import tkFileDialog
    import tkColorChooser
except ImportError:
    # Python 3
    from tkinter import *
    from tkinter import ttk
    from tkinter import messagebox as tkMessageBox
    from tkinter import filedialog as tkFileDialog
    from tkinter import colorchooser as tkColorChooser
import AuroraAPI
import time
import AnimationProcessorWrapper
import SdkCompile
import json
import colorsys
import os
import sys
import subprocess
from PluginOptions import PluginOptionsGUI

# to make sure input works on both python 2.x and 3.x
try:
    input = raw_input
except NameError:
    pass
    
class MainGUI:
    def __init__(self):
        self.root = Tk()
        self.root.title("Plugin Builder")
        self.root.minsize(width=0, height=260)
        self.root.maxsize(width=1200, height=260)
        self.root.resizable(width=False, height=False)
        self.mainframe = ttk.Frame(self.root)
        # Known issue with MacOS TCL where the background color of ttk is not defined and different from the Tkinter background color
        operating_sys = sys.platform
        if operating_sys == "darwin":
            self.root.configure(background="#E4E4E4")
        self.plugin_dir_path = StringVar()
        self.plugin_dir_path.trace("w", lambda name, index, mode, var=self.plugin_dir_path:self.plugin_path_updated(var))
        self.src_dir = os.path.dirname(os.path.realpath(__file__));
        self.palette_path = StringVar()
        self.ip_addr = StringVar()
        self.curr_palette_string = StringVar()
        self.directory_divider = "/"
        self.should_use_simulator = IntVar()
        self.sim_proc = None

        self.palette = []
        self.palette_entered = False
        self.saved_auth = ""
        self.curr_palette_string.set("")
        self.sound_module = AnimationProcessorWrapper.AnimationProcessorWrapper(self)
        self.load_palette_from_file()
        self.auth_dir = self.get_auth_dir()
        self.get_auth()
        self.get_os_dir()

        self.pluginOptionsGUI = PluginOptionsGUI(self.root)
        self.pluginOptionsGUI.set_plugin_dir(self.src_dir + "/../AuroraPluginTemplate")

    def plugin_path_updated(self, path):
        self.pluginOptionsGUI.update_plugin_dir(path.get())

    def get_os_dir(self):
        operating_system = sys.platform
        if (operating_system == "darwin" or "linux" in operating_system):
            iprint("Detected unix based system")
            self.directory_divider = "/"
        elif ("win" in operating_system):
            iprint("Detected windows system")
            self.directory_divider = "\\"

    def load_palette_from_file(self):
        iprint("reading in palette from file")
        if (self.plugin_dir_path.get() == "" or self.plugin_metadata.plugin_name.get() == "" ):
            return
        try:
            open_file = open(self.plugin_dir_path.get() + self.directory_divider + "palette", "r")
            self.palette = json.load(open_file)
            self.palette = self.palette['palette']
            dprint("read in palette", self.palette)
            open_file.close()
        except ValueError:
            iprint("No existing palette file")
            self.palette = []
            self.curr_palette_string.set("")
        except IOError:
            iprint("No existing palette file")
            self.palette = []
            self.curr_palette_string.set("")

    def get_plugin_dir(self):
        self.plugin_dir_path.set(tkFileDialog.askdirectory())

    def build_plugin(self):
        if self.plugin_dir_path.get() == "":
            tkMessageBox.showerror("Error", "No plugin to build")
            return
        SdkCompile.sdk_compile(self.plugin_dir_path.get())
        dprint("palette", self.palette)
        self.write_palette_for_sdk()
        if self.pluginOptionsGUI.has_plugin_options():
            self.pluginOptionsGUI.generate_plugin_options_header(False)

    def play_plugin(self):
        if self.plugin_dir_path.get() == "":
            tkMessageBox.showerror("Error", "No plugin to play")
            return
        if self.ip_addr.get() == "" and self.should_use_simulator.get() == 0:
            tkMessageBox.showerror("Error", "No IP Address")
            return
        if self.pluginOptionsGUI.has_plugin_options():
            if self.pluginOptionsGUI.generate_plugin_options_header(False) == -1:
                return
        if (self.should_use_simulator.get() == 1):
            if self.sim_proc == None:
                path = ""
                if sys.version_info < (3, 0):
                    path = "../LightPanelsSimulator/py27/light-panels-simulator.py"
                elif sys.version_info >= (3, 4):
                    path = "../LightPanelsSimulator/py3/light-panels-simulator.py"
                elif sys.version_info >= (3, 0) and sys.version_info < (3, 4):
                    print("Requires Python 2.7 or Python 3.4+")
                iprint("launching simulator")
                command = ["python", path]
                self.sim_proc = subprocess.Popen(command, cwd=self.src_dir, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        else:
            while (not self.test_auth()):
                self.authenticate_with_aurora()
            time.sleep(0.5)

        iprint("Playing plugin")
        self.sound_module.run_music_processor()
        time.sleep(1)
        iprint("Playing music processor")
        use_plugin_options = self.pluginOptionsGUI.has_plugin_options()
        self.sound_module.run_thread(self.ip_addr.get(), self.plugin_dir_path.get(), self.palette_path.get(), self.palette_entered, self.should_use_simulator.get(), use_plugin_options)

    def stop_plugin(self):
        iprint("Stopping plugin")
        self.sound_module.stop()
        time.sleep(1)
        iprint("Stopping music processor")
        self.sound_module.stop_music_proc()
        if self.sim_proc != None:
            if self.sim_proc.poll() == None:
                iprint("killing aurora simulator")
                self.sim_proc.kill()
            self.sim_proc = None

    def add_color_to_palette(self):
        if (self.curr_palette_string.get() == ""):
            self.palette = [] # this is in case the default palette has already been used in a previous build
        color = tkColorChooser.askcolor()
        dprint("New color added to palette", color)
        rgb_color = color[0]
        hsv_color = colorsys.rgb_to_hsv(rgb_color[0]/255.0, rgb_color[1]/255.0, rgb_color[2]/255.0)
        hsv = {"hue": int(hsv_color[0]*360), "saturation": int(hsv_color[1]*100), "brightness": int(hsv_color[2]*100)}
        self.palette.append(hsv)
        self.curr_palette_string.set(self.curr_palette_string.get() + json.dumps(hsv) + '\n')

    def test_auth(self):
        self.get_auth()
        if (self.saved_auth == ""):
            iprint("No saved auth.")
            return False
        iprint("testing auth on " + str(self.ip_addr.get()) + " with token: " + str(self.saved_auth))
        AuroraAPI.setIPAddr(self.ip_addr.get())
        uri = AuroraAPI.v1getUri(self.saved_auth, "effects/effectsList")
        status, reason, body = AuroraAPI.send("GET", uri, "")
        dprint("status", status)
        if (str(status) == "401"):
            return False
        return True

    def authenticate_with_aurora(self):
        if (self.test_auth()):
            iprint("Already Paired")
        else:
            input("Press the power button on the controller for 5 to 7 seconds. Then press enter.")
            AuroraAPI.setIPAddr(self.ip_addr.get())
            status, auth_token = AuroraAPI.request_token()
            iprint("Authenticating with aurora, got auth token: " + str(auth_token))
            self.save_auth(auth_token)

    def get_auth_dir(self):
        cwd = self.src_dir.split(self.directory_divider)
        cwd = cwd[:len(cwd) - 1]
        path = self.directory_divider.join(cwd) + self.directory_divider + "auth_tokens"
        return path
        
    def get_auth(self):
        try:
            open_file = open(self.auth_dir, 'r')
            auth_token = open_file.read()
            iprint("Found auth token: " + str(auth_token))
            self.saved_auth = auth_token
            open_file.close()
        except IOError:
            iprint("No such file or directory")

    def save_auth(self,auth_token):
        self.saved_auth = auth_token
        open_file = open(self.auth_dir, 'w')
        open_file.write(auth_token)
        open_file.close()
        iprint("Saved new auth token: " + str(auth_token) + " at: " + str(self.auth_dir))

    def clear_palette(self):
        self.palette = []
        self.curr_palette_string.set('')

    def toggle_aurora_simulator(self):
        if (self.should_use_simulator.get() == 1):
            self.pair_button.state(["disabled"])
            self.pair_entry.state(["disabled"])
        else:
            self.pair_button.state(["!disabled"])
            self.pair_entry.state(["!disabled"])

    def show_window(self):
        self.mainframe.grid(column=0, row=0, sticky=(N, W, E, S))
        self.mainframe.columnconfigure(0, weight=1)
        self.mainframe.rowconfigure(0, weight=1)

        ttk.Label(self.mainframe, text="             ").grid(column=0, row=0, sticky=(N,W))
        ttk.Label(self.mainframe, text='1. Pair your Light Panels   ').grid(column=1, row=1, sticky=(N, W))
        ttk.Checkbutton(self.mainframe, variable=self.should_use_simulator, text='Use Light Panels Simulator', command=self.toggle_aurora_simulator).grid(column=2, row=1, sticky=(N,W))

        ttk.Label(self.mainframe, text='IP Address').grid(column=1, row=2, sticky=(N, W))
        self.pair_entry = ttk.Entry(self.mainframe, width=35, textvariable=self.ip_addr)
        self.pair_entry.grid(column=2, row=2, columnspan=2, sticky=(N, W))
        self.pair_button = ttk.Button(self.mainframe, width=12, text='Pair', command=self.authenticate_with_aurora)
        self.pair_button.grid(column=4, row=2, sticky=(N,W))

        ttk.Label(self.mainframe, text='2. Make a color palette').grid(column=1, row=3, sticky=(N, W))

        ttk.Button(self.mainframe, text="Add Color", command=self.add_color_to_palette).grid(column=1, row=4, sticky=(N, W))
        ttk.Label(self.mainframe, textvariable=self.curr_palette_string, wraplength=500).grid(column=2, row=4, columnspan=2, sticky=(N, W))
        ttk.Button(self.mainframe, width=12, text="Clear palette", command=self.clear_palette).grid(column=4, row=4, sticky=(N, W))

        ttk.Label(self.mainframe, text='3. Build your plugin').grid(column=1, row=5, sticky=(N, W))
        
        ttk.Label(self.mainframe, text='Plugin Location').grid(column=1, row=6, sticky=(N, W))
        ttk.Entry(self.mainframe, width=35, textvariable=self.plugin_dir_path).grid(column=2, row=6, columnspan=2, sticky=(N, W))
        ttk.Button(self.mainframe, width=12, text='Browse', command=self.get_plugin_dir).grid(column=4, row=6, sticky=(N, W))
    
        ttk.Button(self.mainframe, text='Build', command=self.build_plugin).grid(column=2, row=7, columnspan=1, sticky=(N,E))
        ttk.Button(self.mainframe, text='Upload & Run', command=self.play_plugin).grid(column=3, row=7, columnspan=1, sticky=N)
        ttk.Button(self.mainframe, width=12, text='Stop Plugin', command=self.stop_plugin).grid(column=4, row=7, columnspan=1, sticky=(N, W))

        ttk.Label(self.mainframe, text="             ").grid(column=5, row=8, sticky=(N,W))
        ttk.Label(self.mainframe, text="             ").grid(column=5, row=9, sticky=(N,W))

        self.pluginOptionsGUI.create_plugin_frame()

        self.root.mainloop()

    def write_palette_for_sdk(self):
        iprint("writing out palette to file")
        self.palette_path.set(self.plugin_dir_path.get() + self.directory_divider + "palette")
        if self.plugin_dir_path.get() == "":
            tkMessageBox.showerror("Error", "Please enter the path to the plugin")
            return;
        try:
            open_file = open(self.plugin_dir_path.get() + self.directory_divider + "palette", "w+")
        except IOError as errinfo:
            tkMessageBox.showerror("Error", "Could not write to directory." + str(errinfo))
            return
        palette_dict = self.palette
        try:
            palette_dict["palette"]
        except TypeError:
            palette_dict = {}
            palette_dict["palette"] = self.palette
        self.palette_entered = (len(self.palette) > 0)
        
        open_file.write(json.dumps(palette_dict))
        open_file.close()


if __name__ == "__main__":
    mainGUI = MainGUI()
    mainGUI.show_window()
    mainGUI.stop_plugin()
