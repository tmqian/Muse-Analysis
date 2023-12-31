import numpy as np
import matplotlib.pyplot as plt
import sys

from matplotlib.gridspec import GridSpec
from scipy.signal import savgol_filter
from scipy.optimize import curve_fit

'''
Muse Analysis for NIDAC data
usage: python MuseAnalysis/DoubleProbe.py data/231219083/

be sure to include '/' at end of shot path

Updated 22 Dec 2023
'''


class DoubleProbe():

    def __init__(self,fin):

        self.fname = fin
        self.loadData(fin)


    def loadData(self,fin, 
                      V_FACTOR=40/1.76, # to V
                      I_FACTOR=4e-2/0.85, # to mA
                    ):
        '''
        after 12/22 use Vfac=40/1.76, Ifac=4e-2/0.85
        12/19 data uses Vfac=10, Ifac=97.8757/5
        '''

        data = np.genfromtxt(fin,delimiter=',')

        time_long, AI0, AI1, AI2, AI3, AO0, AO1 = data.T  # s
        self.unix_time = time_long
        self.AI0 = AI0  # pressure
        self.AI1 = AI1  # floating probe
        self.AI2 = AI2  # bias
        self.AI3 = AI3  # shunt
        self.AO0 = AO0  # bias request
        self.AO1 = AO1  # unused

        self.time = time_long - time_long[0] # seconds

        self.V_factor = V_FACTOR
        self.I_factor = I_FACTOR
   

    def plotRaw(self,
                     sg_window = 50, # savgol window
                     sg_order = 3, # savgol polynomial order
                      save=False):
        '''
        Show raw data from all NIdac channels.
        '''

        time_long = self.unix_time
        pressure = self.AI0
        V_bias_request = self.AO0 
        V_bias = self.AI2
        V_shunt = self.AI3
        V_float = self.AI1

        # fits
        fpressure = savgol_filter(pressure, sg_window, sg_order)
        fV_bias_request = savgol_filter(V_bias_request, sg_window, sg_order)
        fV_bias = savgol_filter(V_bias, sg_window, sg_order)
        fV_shunt = savgol_filter(V_shunt, sg_window, sg_order)
        fV_float = savgol_filter(V_float, sg_window, sg_order)

        # raw data 
        fig,axs = plt.subplots(6,1, figsize=(10,8))
        axs[0].plot(time_long, '.', label='time')
        axs[1].plot(pressure, '.', label='pressure')
        axs[2].plot(V_bias_request, '.', label='bias request') #5x
        axs[3].plot(V_bias, '.', label='bias') # 10x
        axs[4].plot(V_shunt, '.', label='shunt') # divide by 5, multiply 97 gain, divide by 1kOhm
        axs[5].plot(V_float, '.', label='float') # divide by 5, multiply 97 gain, divide by 1kOhm

        axs[1].plot(fpressure, 'C2--')
        axs[2].plot(fV_bias_request, 'C2--')
        axs[3].plot(fV_bias, 'C2--')
        axs[4].plot(fV_shunt, 'C2--')
        axs[5].plot(fV_float, 'C2--')
        
        axs[-1].set_xlabel("integer count")
        for a in axs:
            a.legend(loc=0)
            a.grid()
            
        fig.suptitle(self.fname)
        plt.tight_layout()

        if save:
            fig.savefig(save)


    def plotIV(self, t0=2.2, # crop start time
                     t1=6.8, # crop finish time
                     sg_window = 50, # savgol window
                     sg_order = 3, # savgol polynomial order
                     Area_probe_m2 = 6.8e-6, # probe area
                     plot = True,
                     save = False,
                     ):
        '''
        Plot V(t) I(t) I(V)
        Add filtering and fit to I-V tanh.
        '''

        # should code the conversion in ONE place to avoid bugs
        V_probe = self.AI2 * self.V_factor  # V
        I_probe = self.AI3 * self.I_factor # mA
        time = self.time # s

        self.V = V_probe
        self.I = I_probe

        def argNear(arr,val):
            return np.argmin( np.abs(arr - val) )

        t0_idx = argNear(time,t0)
        t1_idx = argNear(time,t1)

        # cut
        V_cut = V_probe[t0_idx:t1_idx]
        I_cut = I_probe[t0_idx:t1_idx]
        t_cut = time[t0_idx:t1_idx]

        # filter
        V_filter = savgol_filter(V_cut, sg_window, sg_order)
        I_filter = savgol_filter(I_cut, sg_window, sg_order)

        # fit
        def IV_tanh(Vbias,Te,Isat,I_offset):
            return Isat * np.tanh( Vbias / 2. / Te ) + I_offset

        # this fit uses cut (but NOT filtered) data
        param, cov = curve_fit(IV_tanh, V_cut, I_cut)
        I_fit = IV_tanh(V_cut,*param)
        Te, Isat, I_offset = param
    
        err = np.sqrt( np.diag(cov) )
        dT, dIsat, dIoff = err

        # this fits filtered data
        param2, cov2 = curve_fit(IV_tanh, V_filter, I_filter)
        I_fit2 = IV_tanh(V_filter,*param2)
        Te2, Isat2, I_offset2 = param2
    
        err2 = np.sqrt( np.diag(cov2) )
        dT2, dIsat2, dIoff2 = err2

        # compute density
        e = 1.6e-19
        A = Area_probe_m2
        m = 938e6 # H, eV 
        c = 2.99e8 # m/s
        I = Isat /1e3 # A
        v = c*np.sqrt(Te/m)
        ne = I / (e * A * v)
        dn = ne * np.sqrt( (dIsat/Isat)**2 + (dT/Te)**2 )

        # plot
        if plot:

            fig = plt.figure(layout="constrained", figsize=(10,6))
            gs = GridSpec(2, 2, figure=fig)
            ax0 = fig.add_subplot(gs[0, 1])
            ax1 = fig.add_subplot(gs[1, 1])
            ax2 = fig.add_subplot(gs[:, 0])

            time = self.time # s
            ax0.plot(time, V_probe, 'C0.', label='V')
            ax1.plot(time, I_probe, 'C1.', label='mA')
            ax2.plot(V_probe, I_probe, 'C4.')

            ax1.set_xlabel('time [s]')
            ax2.set_xlabel('V')
            ax2.set_ylabel('mA')
            ax0.plot(t_cut, V_cut, 'C3.', ms=1, label='cut')
            ax1.plot(t_cut, I_cut, 'C3.', ms=1, label='cut')
            ax2.plot(V_cut, I_cut, 'C3.', ms=1)
    
            ax0.plot(t_cut, V_filter, 'C2--', lw=0.5)
            ax1.plot(t_cut, I_filter, 'C2--', lw=0.5)
            ax2.plot(V_cut, I_filter, 'C2--', lw=2, label=f"filter: savgol (window,order) = {sg_window}, {sg_order}")
    
            ax2.plot(V_cut, I_fit, 'C1:', lw=5, label="fit cut")
            ax2.plot([],[],' ', label=rf"$T_e$ = {Te:.1f}$\pm${dT:.1f} eV")
            ax2.plot([],[],' ', label=r"$I_{sat}$"+rf" = {Isat:.2f}$\pm${dIsat:.2f} mA")
            ax2.plot([],[],' ', label=rf"$n_e$ = {ne/1e16:.1f}$\pm${dn/1e16:.2f}"+r"$\times 10^{16}$ $m^{-3}$")
            ax2.plot([],[],' ', label=r"$I_{offset}$"+rf" = {I_offset:.2f}$\pm${dIoff:.2f} mA")

            ax2.plot(V_filter, I_fit2, 'C3:', lw=5, label="fit filtered")
    
            ax2.set_ylim( 1.1*np.min(I_cut), 1.1*np.max(I_cut) )
    
            [a.legend(loc=0) for a in [ax0,ax1,ax2] ]
            [a.grid() for a in [ax0,ax1,ax2] ]
            fig.suptitle(self.fname)
    
            if save:
                fig.savefig(save)


    def plotPressure(self, axs=None,
                           sg_window = 50, # savgol window
                           sg_order = 3, # savgol polynomial order
                           plotRaw = False, # show the unscaled pressure data
                           t_global = None, # use global time ref to match other diagnostics
                           save = False,
                           ):

        try:
            # set x-axis to global time
            N = len(t_global) # fails if t_global is None
            time = t_global
        except:
            time = self.time

        V = self.AI0

        P_raw = 10**((V - 5.5)/0.5) # V -> P conversion from manual
        P_H2 = P_raw / 0.42 # -> H2 scale factor from manual

        # use savgol filter
        P_raw_filter = savgol_filter(P_raw, sg_window, sg_order)
        P_H2_filter = savgol_filter(P_H2, sg_window, sg_order)

        if axs==None:
            fig,axs = plt.subplots(1,1)
            axs.set_xlabel('s')
            axs.set_title(self.fname)

        axs.plot(time, P_H2, 'C0.', label="pressure H2")
        axs.plot(time, P_H2_filter, 'C1.')

        if plotRaw:
            axs.plot(time, P_raw, 'C2.', label="pressure observed (N2)")
            axs.plot(time, P_raw_filter, 'C4.')
  
        axs.set_ylabel('Torr')
        axs.ticklabel_format(axis='y', style='sci', scilimits=(0,0) )

        axs.legend()
        axs.grid()

        if save:
            fig.savefig(save)


if __name__ == '__main__':
    path = sys.argv[1]
    data = DoubleProbe(path+"NIDAQtext.txt")
    
    data.plotRaw()
    data.plotIV()
    data.plotPressure()
    
    plt.show()
    

