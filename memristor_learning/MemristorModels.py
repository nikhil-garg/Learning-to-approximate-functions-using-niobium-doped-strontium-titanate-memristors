import numpy as np
import math


class MemristorPair:
    def __init__( self, model, seed=None, voltage_converter=None, base_voltage=1e-1, gain=1e5 ):
        self.mem_one = model( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        self.mem_two = model( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        
        self.seed = seed
    
    def pulse( self, signal ):
        raise NotImplementedError
    
    def get_state( self, value="conductance", scaled=True, gain=10**4 ):
        return self.mem_one.get_state( value, scaled, gain ) - self.mem_two.get_state( value, scaled, gain )
    
    def save_state( self ):
        history_one = self.mem_one.save_state()
        history_two = self.mem_two.save_state()
    
    def plot_state( self, value, i, j, range, ax, c, combined=False ):
        if value == "resistance":
            tmp_plus = self.mem_one.history
            tmp_minus = self.mem_two.history
        if value == "conductance":
            tmp_plus = np.divide( 1, self.mem_one.history )
            tmp_minus = np.divide( 1, self.mem_two.history )
        ax.plot( range, tmp_plus, c="r", label='Excitatory' )
        ax.plot( range, tmp_minus, c="b", label='Inhibitory' )
        if not combined:
            ax.annotate( str( j + 1 ) + "->" + str( i + 1 ), xy=(range[ 0 ], tmp_plus[ 0 ]), c="r" )
            ax.annotate( str( j + 1 ) + "->" + str( i + 1 ), xy=(range[ 0 ], tmp_minus[ 0 ]), c="b" )
        if combined:
            ax.set_title( str( j + 1 ) + "->" + str( i + 1 ) )
            # ax.label_outer()
            # ax.set_yticklabels( [ ] )


class MemristorPlusMinus( MemristorPair ):
    def __init__( self, model, seed=None, voltage_converter=None, base_voltage=1e-1, gain=1e5 ):
        super().__init__( model, seed, voltage_converter, base_voltage, gain )
    
    # on positive feedback the excitatory memristor gets exponent pulse
    def pulse( self, signal ):
        if signal > 0:
            self.mem_one.pulse( signal )
        if signal < 0:
            self.mem_two.pulse( -signal )
        
        return self.mem_one.get_state() - self.mem_two.get_state()


class MemristorComplementary( MemristorPair ):
    def __init__( self, model, seed=None, voltage_converter=None, base_voltage=1e-1, gain=1e5 ):
        super().__init__( model, seed, voltage_converter, base_voltage, gain )
    
    def pulse( self, signal ):
        if signal > 0:
            self.mem_one.pulse( signal )
            self.mem_two.pulse( -signal )
        if signal < 0:
            self.mem_one.pulse( -signal )
            self.mem_two.pulse( signal )
        
        return self.mem_one.get_state() - self.mem_two.get_state()


class Memristor:
    def __init__( self, seed=None, voltage_converter=None, base_voltage=1e-1, gain=1e5 ):
        # save resistance history for later analysis
        self.history = [ ]
        
        self.r_curr = None
        self.r_1 = None
        self.r_0 = None
        
        self.seed = seed
        self.voltage_converter = voltage_converter
        self.base_voltage = base_voltage
        self.gain = gain
        
        # Weight initialisation
        import random
        random.seed( self.seed )
        
        self.r_curr = random.uniform( 1e8, 1.1e8 )
    
    # pulse the memristor with exponent tension
    def pulse( self, signal ):
        V = np.sign( signal ) * self.base_voltage
        # if signal is zero we needn't make any adjustments
        num_steps = self.voltage_converter( signal ) if signal != 0 else 0
        
        for _ in range( num_steps ):
            pulse_number = self.compute_pulse_number( self.r_curr, V )
            self.r_curr = self.compute_resistance( pulse_number + 1, V )
        
        return self.get_state( gain=self.gain )
    
    def compute_pulse_number( self, R, V ):
        raise NotImplementedError
    
    def compute_resistance( self, n, V ):
        raise NotImplementedError
    
    def get_state( self, value="conductance", scaled=True, gain=1e5 ):
        epsilon = np.finfo( float ).eps
        
        if value == "conductance":
            g_curr = 1.0 / self.r_curr
            g_min = 1.0 / self.r_1
            g_max = 1.0 / self.r_0
            if scaled:
                ret_val = ((g_curr - g_min) / (g_max - g_min)) + epsilon
            else:
                ret_val = g_curr + epsilon
        
        if value == "resistance":
            if scaled:
                ret_val = ((self.r_curr - self.r_0) / (self.r_1 - self.r_0)) + epsilon
            else:
                ret_val = self.r_curr + epsilon
        
        return gain * ret_val
    
    def save_state( self ):
        self.history.append( self.r_curr )
    
    def plot_state( self, value, i, j, range, ax, c, combined=False ):
        if value == "resistance":
            tmp = self.history
        if value == "conductance":
            tmp = np.divide( 1.0, self.history )
        
        ax.plot( range, tmp, c=c )
        # ax.annotate( "(" + str( i ), xy=(10, 10) )
    
    def plot_memristor_curve_exhaustive( self, V=1, threshold=1000, step=10, n_steps=math.inf, start_r=None,
                                         interpolate_after_threshold=True ):
        import matplotlib.pyplot as plt
        import sys, time
        from memristor_learning.MemristorHelpers import expand_interpolate
        
        x = [ ]
        y = [ ]
        n = 1
        it = 1
        r_curr = self.r_1 if V >= 0 else self.r_0
        if start_r:
            r_curr = start_r
            n = self.compute_pulse_number( r_curr, V )
        
        def thresh():
            if V >= 0 and r_curr >= self.r_0 + threshold:
                return True
            elif V < 0 and r_curr <= self.r_1 - threshold:
                return True
            else:
                return False
        
        start_time = time.time()
        while thresh() and n < n_steps:
            x.append( n )
            y.append( r_curr )
            
            r_curr = self.compute_resistance( n, V )
            sys.stdout.write( f"\rIteration {it}"
                              f", time {round( time.time() - start_time, 2 )}:"
                              f" resistance {self.r_0}/{round( r_curr, 2 )}/{self.r_1}"
                              f", threshold {threshold}"
                              f", step {step}" )
            n += step
            it += 1
            sys.stdout.flush()
        print( f"\n{round( time.time() - start_time, 2 )} seconds elapsed for exhaustive step" )
        
        if interpolate_after_threshold:
            start_time = time.time()
            x_limit = self.r_0 + threshold if V >= 0 else self.r_1 - threshold
            y_limit = self.r_0 if V >= 0 else self.r_1
            # subdivide remaining range into blocks of equal step size
            oldx = np.array( [ x[ -1 ], x[ -1 ] + round( x_limit / step, 1 ) ] )
            # interpolate from last real value to the theoretical maximum
            oldy = np.array( [ y[ -1 ], y_limit ] )
            int_length, newx, newy = expand_interpolate( oldx, oldy, step=step, include_end=True )
            
            x = np.array( x )
            x = np.append( x, newx )
            y = np.array( y )
            y = np.append( y, newy )
            
            print( f"\n{round( time.time() - start_time, 2 )} seconds elapsed for interpolation step" )
        
        derivative = np.abs( np.gradient( y, x ) )
        second_derivative = np.abs( np.gradient( derivative, x ) )
        
        fig, (ax1, ax3) = plt.subplots( 2 )
        ax1.plot( x, y )
        # ax2.plot( x, y )
        ax3.plot( x, derivative )
        # ax4.plot( x, second_derivative )
        ax1.set_title( "Linear" )
        # ax2.set_title( "Log" )
        ax3.set_title( "Derivative" )
        # ax4.set_title( "Second derivative" )
        # ax2.set_yscale( "log" )
        plt.xlabel( "Pulses (n)" )
        ax1.set_ylabel( "Resistance (R)" )
        plt.grid( alpha=.4, linestyle='--' )
        plt.show()
        #
        # import pickle
        # with open( "../data/memristor_curve.pkl", "wb" ) as f:
        #     pickle.dump( zip( x, y ), f )
        
        return np.array( x ), np.array( y ), derivative, second_derivative
    
    def plot_memristor_curve_interpolate( self, V=1, threshold=1000 ):
        import matplotlib.pyplot as plt
        from math import fabs, floor
        from memristor_learning.MemristorHelpers import expand_interpolate
        
        c = self.a + self.b * V
        
        x = [ ]
        y = [ ]
        n = 0
        step = 1
        r_curr = self.r_1
        
        from tqdm import tqdm
        with tqdm( total=self.r_1 - (self.r_0 + threshold) ) as pbar:
            r_pre = r_curr
            n += step
            r_curr = self.compute_resistance( n, V )
            r_diff = fabs( r_curr - r_pre )
            step += floor( 1 / r_diff )
            
            x.append( n )
            y.append( r_curr )
            
            pbar.update( n )
        
        c = 0
        
        with tqdm( total=x[ -1 ] ) as pbar:
            while c < len( x ):
                int_length, newx, newy = expand_interpolate( x[ c:c + 2 ], y[ c:c + 2 ] )
                if newx is not None:
                    for cc, (xx, yy) in enumerate( zip( newx, newy ) ):
                        x.insert( c + cc + 1, xx )
                        y.insert( c + cc + 1, yy )
                c += int_length
                pbar.update( int_length )
        
        plt.plot( x, y )
        plt.yscale( 'log' )
        plt.xlabel( "Pulses (n)" )
        plt.ylabel( "Resistance (R)" )
        plt.grid( alpha=.4, linestyle='--' )
        plt.show()


class OnedirectionalPowerlawMemristor( Memristor ):
    def __init__( self, a, r_0, r_1, seed=None, voltage_converter=None, base_voltage=None, gain=1e5 ):
        super().__init__( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        
        self.a = a
        self.r_0 = r_0
        self.r_1 = r_1
    
    def compute_pulse_number( self, R, V ):
        if V >= 0:
            return ((R - self.r_0) / self.r_1)**(1 / self.a)
    
    def compute_resistance( self, n, V ):
        if V > 0:
            return self.r_0 + self.r_1 * n**self.a
        else:
            return self.r_curr


class BidirectionalPowerlawMemristor( Memristor ):
    def __init__( self, a, c, r_0, r_1, seed=None, voltage_converter=None, base_voltage=None, gain=1e3 ):
        super().__init__( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        
        self.a = a
        self.c = c
        self.r_0 = r_0
        self.r_1 = r_1
        
        self.r_3 = 1e9
    
    def compute_pulse_number( self, R, V ):
        if V >= 0:
            return ((R - self.r_0) / self.r_1)**(1 / self.a)
        else:
            return ((self.r_3 - R) / self.r_3)**(1 / self.c)
    
    def compute_resistance( self, n, V ):
        if V > 0:
            return self.r_0 + self.r_1 * n**self.a
        elif V < 0:
            return self.r_3 - self.r_3 * n**self.c
        else:
            return self.r_curr


class MemristorAnouk( Memristor ):
    def __init__( self, r0=100, r1=2.5 * 10**8, a=-0.128, b=-0.522, seed=None, voltage_converter=None,
                  base_voltage=1e-1, gain=1e5 ):
        super().__init__( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        # set parameters of device
        self.r_0 = r0
        self.r_1 = r1
        self.a = a
        self.b = b
    
    def compute_pulse_number( self, R, V ):
        return ((R - self.r_0) / self.r_1)**(1 / (self.a + self.b * V))
    
    def compute_resistance( self, n, V ):
        return self.r_0 + self.r_1 * n**(self.a + self.b * V)


class MemristorAnoukBidirectional( Memristor ):
    def __init__( self, r0=100, r1=2.5 * 10**8, a=-0.128, b=-0.522, c=-0.128, d=-0.522, seed=None,
                  voltage_converter=None, base_voltage=1e-1, gain=1e3 ):
        super().__init__( seed=seed, voltage_converter=voltage_converter, base_voltage=base_voltage, gain=gain )
        # set parameters of device
        self.r_0 = r0
        self.r_1 = r1
        self.a = a
        self.b = b
        self.c = c
        self.d = d
    
    def compute_pulse_number( self, R, V ):
        r3 = 1e9
        if V >= 0:
            return ((R - self.r_0) / self.r_1)**(1 / (self.a + self.b * V))
        else:
            # return (1 - ((R - self.r_0) / self.r_1))**(1 / (self.c + self.d * -V))
            # Niels'
            return ((r3 - R) / r3)**(1 / (self.c + self.d * -V))
    
    def compute_resistance( self, n, V ):
        r3 = 1e9
        if V > 0:
            return self.r_0 + self.r_1 * n**(self.a + self.b * V)
        elif V < 0:
            # return self.r_0 + self.r_1 * (1 - n**(self.c + self.d * -V))
            # Niels'
            return r3 - r3 * n**(self.c + self.d * -V)
        else:
            return self.r_curr
