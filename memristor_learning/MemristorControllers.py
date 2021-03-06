from memristor_learning.MemristorModels import *
import numpy as np


class VoltageConverter:
    def __init__( self, levels=1 ):
        self.levels = levels
    
    def __call__( self, signal ):
        return 1


class LevelsVoltageConverter( VoltageConverter ):
    def __init__( self, levels=10 ):
        super().__init__( levels=levels )
        
        self.smallest_seen = 0
        self.largest_seen = 0
    
    def __call__( self, signal ):
        # update extremes of the range at each call
        if signal < self.smallest_seen:
            self.smallest_seen = signal
        if signal > self.largest_seen:
            self.largest_seen = signal
        
        # calculate array containining the ranges
        steps = np.linspace( self.smallest_seen, self.largest_seen, num=self.levels )
        # return index+1=number of steps for this signal
        num_steps = np.searchsorted( steps, signal, side="right" )
        
        return num_steps


class MemristorController:
    def __init__( self, model, learning_rule, in_size, out_size,
                  dt=0.001, logging=True, seed=None, weight_modifier=lambda x: x, voltage_converter=lambda x: x,
                  base_voltage=1e-1, gain=1e5 ):
        self.memristor_model = model
        
        self.input_size = in_size
        self.output_size = out_size
        
        self.dt = dt
        
        self.weights = None
        self.memristors = None
        self.voltage_converter = voltage_converter
        self.base_voltage = base_voltage
        self.gain = gain
        
        # initialize learning rule parameters
        self.learning_rule = learning_rule
        self.learning_rule.input_size = in_size
        self.learning_rule.output_size = out_size
        self.learning_rule.logging = logging
        self.learning_rule.weight_modifier = weight_modifier
        self.learning_rule.dt = dt
        
        # save for analysis
        self.logging = logging
        self.weight_history = [ ]
        self.error_history = [ ]
        self.conductance_history = [ ]
        
        self.seed = seed
    
    def get_components( self ):
        return self.memristors.flatten()
    
    def save_state( self ):
        for j in range( self.output_size ):
            for i in range( self.input_size ):
                self.memristors[ j, i ].save_state()
    
    def plot_state( self, sim, value, err_probe=None, combined=False, time=None, figsize=None, ylim=None ):
        import datetime
        import matplotlib.pyplot as plt
        from matplotlib.pyplot import cm
        from nengo.utils.matplotlib import rasterplot
        
        # plot memristor resistance and error
        # plt.suptitle( datetime.datetime.now().strftime( '%H:%M:%S %d-%m-%Y' ) )
        if not combined:
            fig, axes = plt.subplots( figsize=figsize )
        if combined:
            fig, axes = plt.subplots( self.output_size, self.input_size, figsize=figsize )
        plt.xlabel( "Post neurons on rows\nPre neurons on columns" )
        if ylim is not None:
            plt.setp( axes, ylim=ylim )
        
        # fig.suptitle( "Memristor " + value, fontsize=16 )
        colour = iter( cm.rainbow( np.linspace( 0, 1, self.memristors.size ) ) )
        for i in range( self.memristors.shape[ 0 ] ):
            for j in range( self.memristors.shape[ 1 ] ):
                c = next( colour )
                if not combined:
                    self.memristors[ i, j ].plot_state( value, i, j, sim.trange(), axes, c, combined )
                    if time:
                        time = int( time )
                        for t in range( time ):
                            axes.axvline( x=t, c="k" )
                if combined:
                    self.memristors[ i, j ].plot_state( value, i, j, sim.trange(), axes[ i, j ], c, combined )
                    if time:
                        time = int( time )
                        for t in range( time ):
                            axes[ i, j ].axvline( x=t, c="k" )
        if err_probe:
            ax2 = plt.twinx()
            ax2.plot( sim.trange(), sim.data[ err_probe ], c="r", label="Error" )
        
        return fig
    
    def plot_weight_matrix( self, time, normalized=False ):
        import matplotlib.pyplot as plt
        from decimal import Decimal
        
        weights_at_time = self.weight_history[ int( time / self.dt ) ]
        
        fig, ax = plt.subplots()
        
        ax.matshow( weights_at_time, cmap=plt.cm.Blues )
        max_weight = np.amax( weights_at_time )
        min_weight = np.amin( weights_at_time )
        
        for i in range( weights_at_time.shape[ 0 ] ):
            for j in range( weights_at_time.shape[ 1 ] ):
                if np.all( weights_at_time == 0 ):
                    c = "0.00"
                else:
                    if normalized:
                        c = str( round( (weights_at_time[ j, i ] - min_weight) / (max_weight - min_weight), 2 ) )
                    else:
                        c = f"{Decimal( weights_at_time[ j, i ] ):.2E}"
                ax.text( i, j, c, va='center', ha='center' )
        plt.title( "Weights at t=" + str( time ) )
        
        return fig
    
    def plot_conductance_matrix( self, time ):
        import matplotlib.pyplot as plt
        from decimal import Decimal
        
        conductances_at_time = self.conductance_history[ int( time / self.dt ) ]
        
        fig, ax = plt.subplots()
        
        ax.matshow( conductances_at_time, cmap=plt.cm.Blues )
        
        for i in range( conductances_at_time.shape[ 0 ] ):
            for j in range( conductances_at_time.shape[ 1 ] ):
                c = f"{Decimal( conductances_at_time[ j, i ] ):.2E}"
                ax.text( i, j, c, va='center', ha='center' )
        plt.title( "Conductances at t=" + str( time ) )
        
        return fig
    
    def get_stats( self, time, select ):
        
        data = self.get_history( select )
        data_at_time = data[ int( time[ 0 ] / self.dt ):int( time[ 1 ] / self.dt ) ]
        
        stats = { }
        stats[ "max" ] = np.amax( data_at_time )
        stats[ "min" ] = np.amin( data_at_time )
        stats[ "mean" ] = np.mean( data_at_time )
        
        return stats
    
    def get_history( self, select ):
        if select == "weight":
            return self.weight_history
        if select == "error":
            return self.error_history
        if select == "conductance":
            return self.conductance_history


class MemristorArray( MemristorController ):
    def __init__( self, model, learning_rule, in_size, out_size, seed=None, voltage_converter=lambda x: x,
                  weight_modifier=lambda x: x,
                  base_voltage=1e-1, gain=1e5 ):
        super().__init__( model, learning_rule, in_size, out_size, seed=seed, voltage_converter=voltage_converter,
                          weight_modifier=weight_modifier,
                          base_voltage=base_voltage, gain=gain )
        
        # to hold future weights
        self.weights = np.zeros( (self.output_size, self.input_size), dtype=np.float )
        
        # create memristor array that implement the weights
        self.memristors = np.empty( (self.output_size, self.input_size), dtype=Memristor )
        for i in range( self.output_size ):
            for j in range( self.input_size ):
                self.memristors[ i, j ] = self.memristor_model( seed=seed, voltage_converter=self.voltage_converter,
                                                                base_voltage=self.base_voltage, gain=self.gain )
                self.weights[ i, j ] = self.memristors[ i, j ].get_state()
        
        self.learning_rule.weights = self.weights
        self.learning_rule.memristors = self.memristors
    
    def __call__( self, t, x ):
        if self.learning_rule.has_learning_signal:
            input_activities = x[ :-1 ]
            learning = np.rint( x[ -1 ] )
            if learning:
                ret = self.learning_rule( t, input_activities )
            else:
                if self.learning_rule.has_error_signal:
                    ret = np.dot( self.weights, input_activities[ :self.input_size ] )
                else:
                    ret = np.dot( self.weights, input_activities )
        else:
            ret = self.learning_rule( t, x )
        
        if self.logging:
            try:
                self.error_history.append( self.learning_rule.get_error_signal() )
            except:
                pass
            self.weight_history.append( self.weights.copy() )
            self.save_state()
            conductances = np.zeros( (self.output_size, self.input_size), dtype=np.float )
            for i in range( self.output_size ):
                for j in range( self.input_size ):
                    conductances[ j, i ] = self.memristors[ j, i ].get_state( value="conductance", scaled=False,
                                                                              gain=1 )
            self.conductance_history.append( conductances )
        
        return ret
