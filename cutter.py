import os
import numpy as np
import audio2numpy
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

class CutterIt :
    '''
    - Input: .mp4 or mp3 file
    - task: cutter silent part or keep only silent part 

    Parameter
        - cut_duration_sec: second for removing or keeping, if silent longer than
        - smooth_add_sec: smoother add for not cutting immeadely when silent

    Return :
       complete .mp4 or .mp3 file
    '''
    def __init__(self, filepath: str, cut_duration_sec = 0.7, smooth_add_sec = 0.15) :
        os.makedirs('temp', exist_ok=True)
        self.filepath = filepath
        self.filename = self.filepath[:-4]
        self.filetype = self.filepath[-3:]
        self.cut_duration_sec = cut_duration_sec
        self.smooth_add_sec = smooth_add_sec
        assert self.cut_duration_sec >= self.smooth_add_sec*2 , 'cut_duration_sec must longer than 2* smooth_add_sec'

        if self.filetype == 'mp4':
            self.array, self.rate = self.video2array()
            self.typer = VideoFileClip(filepath)
        else :
            self.array, self.rate = self.audio2array(self.filepath)
            self.typer = AudioFileClip(filepath)

    def video2array(self) :
        # video to audio
        audio_path = f'temp/{self.filename}.mp3'
        video = VideoFileClip(self.filepath)
        video.audio.write_audiofile(audio_path, verbose=False, logger=None)
        # audio to array
        return self.audio2array(audio_path)
    
    def audio2array(self, audio_path: str) :
        # audio to array
        array, rate = audio2numpy.audio_from_file(path=audio_path)
        if array.shape[-1] != 1 : array = array[:,0]
        array = np.maximum(array, 0).astype(np.float16) # delete all negative value
        return array, rate
    
    def sec2rate(self, sec: int) :
        '''convert second to sample rate'''
        return round(sec*self.rate)

    def rate2sec(self, samplerate: int) :
        '''convert sample rate to second'''
        return round(samplerate / self.rate , 2)
    
    def get_under_cuts(self, array: np.array, alpha = 85) :
        '''
        get undercuts list from array.
        
        alpha: percentile for cut point if sound silent than threshold_alpha it'll cut off.
        '''
        threshold = np.percentile(array[array > 0], q=alpha)
        cut_duration_rate = self.sec2rate(self.cut_duration_sec)
        
        under_ts_rate = 0
        is_start_rate = True
        under_cuts = {}
        for rate_count, value in enumerate(array) :
            if value < threshold :
                under_ts_rate += 1
                if is_start_rate : 
                    start_cut = rate_count
                    is_start_rate = False
                if under_ts_rate >= cut_duration_rate :
                    under_cuts[start_cut] = rate_count 
            else :
                # reset every thing
                is_start_rate = True
                under_ts_rate = 0
        
        # undercuts rate to sec
        under_cuts_sec = {}
        reversed_cuts = {} # for use when: {25: 26, 26: 27} -> {25: 27}
        for start_rate, stop_rate in under_cuts.items() :
            start_sec = self.rate2sec(start_rate)
            stop_sec = self.rate2sec(stop_rate)
            under_cuts_sec[start_sec] = stop_sec
            reversed_cuts[stop_sec] = start_sec

        # {25: 26, 26: 27} -> {25: 27}
        remove_start_sec = []
        for start_sec, stop_sec in under_cuts_sec.items() :
            if start_sec in under_cuts_sec.values() :
                under_cuts_sec[reversed_cuts[start_sec]] = stop_sec
                remove_start_sec.append(start_sec)
        # remove key {25: 27, 26: 27} -> {25: 27}
        for start_sec in remove_start_sec :
            under_cuts_sec.pop(start_sec)

        return under_cuts_sec
    
    def get_undercuts_smooth(self, under_cuts_sec: dict) :
        '''
        add smoother for silent part with smooth_add_sec 

        {12.29: 13.76, 24.9: 25.69} -> {12.39: 13.66, 25.00: 25.59} ; smooth_add_sec = 0.1
        '''
        under_cuts_sec_smooth = {}
        for start_sec, stop_sec in under_cuts_sec.items() :
            under_cuts_sec_smooth[round(start_sec + self.smooth_add_sec, 2)] = round(stop_sec - self.smooth_add_sec, 2)

        return under_cuts_sec_smooth

    def get_keeps_sec(self, under_cuts_sec: list) :
        '''
        get keeps sec from undercuts sec

        {12.29: 13.76, 24.9: 25.69, 26.48: 27.13} -> {0.00: 12.29, 13:76: 24.9, ... }
        '''
        keep_sec = {}
        previous_sec = 0.00
        for start_sec, stop_sec in under_cuts_sec.items() :
            keep_sec[previous_sec] = round(start_sec + self.smooth_add_sec, 2)
            previous_sec = round(stop_sec - self.smooth_add_sec, 2)
        
        return keep_sec
    
    def cutter(self, save_path: str, keeps_sec: list, file_type = 'mp3') :
        '''
        cut silent part then save to save_path
        '''
        if self.filetype == 'mp3' and file_type == 'mp4' :
            raise Exception('mp3 can be save only to mp3 file')

        if self.filetype == 'mp4' and file_type == 'mp3' :
            file = AudioFileClip(f'temp/{self.filename}.mp3')
        else :
            file = self.typer 

        clips_to_keep = []
        for start_sec, stop_sec in keeps_sec.items() :
            clip = file.subclip(start_sec, stop_sec)
            clips_to_keep.append(clip)

        # save_path
        if save_path[-3:] in ['mp3', 'mp4'] :
            save_path = save_path
        else :
            save_path = f'{save_path}.{file_type}'

        if file_type == 'mp4' :
            final_video = concatenate_videoclips(clips_to_keep)
            final_video.write_videofile(save_path, fps=file.fps,  verbose=False, logger=None)
        else :
            final_video = concatenate_audioclips(clips_to_keep)
            final_video.write_audiofile(save_path, verbose=False, logger=None)
        
        # self.remove_temp()

    def remove_temp(self) :
        '''remove temp'''
        [ os.remove(os.path.join('temp', file)) for file in os.listdir('temp') ]
        os.rmdir('temp')

if __name__ == '__main__' :
    cut = CutterIt(filepath='testvideo.mp4')
    array = cut.array
    undercuts = cut.get_under_cuts(array)
    keeps_sec = cut.get_keeps_sec(undercuts)
    cut.cutter('keep_cutter.mp4', keeps_sec, file_type='mp4')

    # if want only silent part
    undercuts_smooth = cut.get_undercuts_smooth(undercuts)
    cut.cutter('silent_part.mp4', undercuts_smooth, file_type='mp4')