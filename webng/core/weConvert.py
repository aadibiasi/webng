from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import yaml, os, shutil, sys, bionetgen
import numpy as np

# TODO: Expose more functionality to the options file
# especially some of them can be optionally exposed
class weConvert:
    """
    This is the class that will be used by the command line tool when it's
    called with the subcommand `webng setup`.

    The class needs the dictionary from configuration YAML file for initalization
    and will use the options there to setup the WESTPA simulation folder.

    The `run` method will use the parsed options and make the WESTPA simulation folder
    using the templates it contains. TODO: Use jinja for templating instead.
    """

    def __init__(self, args):
        """
        take arguments from cement app and get ready to write
        """
        self.opts = self._load_yaml(args.opts)
        self._parse_opts(self.opts)
        # TODO: make this optional somewhere else
        self.copy_run_net = True

    def _getd(self, dic, key, default=None, required=True):
        val = dic.get(key, default)
        if required and (val is None):
            sys.exit("{} is not specified in the dictionary".format(key))
        return val

    def _parse_opts(self, opts_dict):
        """
        Parses the loaded YAML dictionary and updates the
        class attributes appropriately
        """
        # Set the main directory we are in
        self.main_dir = os.getcwd()
        # Propagator options
        propagator_options = self._getd(self.opts, "propagator_options")
        self.propagator_type = self._getd(
            propagator_options, "propagator_type", default="executable"
        )
        if self.propagator_type == "libRoadRunner":
            self.pcoord_list = self._getd(propagator_options, "pcoords")
        # we need to find WESTPA and BNG
        path_options = self._getd(self.opts, "path_options")
        self.WESTPA_path = self._getd(path_options, "WESTPA_path")
        self.bng_path = self._getd(path_options, "bng_path")
        self.bngl_file = self._getd(path_options, "bngl_file")
        self.fname = self._getd(path_options, "sim_name", default="WE_BNG_sim")
        # Define where the BNG2.pl script is
        self.bngpl = os.path.join(self.bng_path, "BNG2.pl")
        # Sampling options
        sampling_options = self._getd(self.opts, "sampling_options")
        self.tau = self._getd(sampling_options, "tau")
        self.max_iter = self._getd(sampling_options, "max_iter", default=100)
        self.dims = self._getd(sampling_options, "dimensions")
        self.plen = self._getd(sampling_options, "pcoord_length")
        # binning options
        binning_options = self._getd(self.opts, "binning_options")
        self.binning_style = self._getd(binning_options, "style", default='adaptive')
        if self.binning_style == 'adaptive':
            self.traj_per_bin = self._getd(binning_options, "traj_per_bin", default=10)
            self.block_size = self._getd(binning_options, "block_size", default=10)
            self.center_freq = self._getd(binning_options, "center_freq", default=1)
            self.max_centers = self._getd(binning_options, "max_centers", default=300)
        else:
            self.first_edge = self._getd(binning_options, "first_edge", default=0)
            self.last_edge = self._getd(binning_options, "last_edge", default=50)
            self.num_bins = self._getd(binning_options, "num_bins", default=10)
            self.traj_per_bin = self._getd(binning_options, "traj_per_bin", default=10)
            self.block_size = self._getd(binning_options, "block_size", default=10)

    def _load_yaml(self, yfile):
        """
        internal function that opens a file and loads it in using
        yaml library
        """
        with open(yfile, "r") as f:
            y = yaml.load(f, Loader=Loader)
        return y

    def _write_librrPropagator(self):
        lines = [
            "from __future__ import division, print_function; __metaclass__ = type",
            "import numpy as np",
            "import westpa, copy, time, random",
            "from westpa.core.propagators import WESTPropagator",
            "import roadrunner as librr",
            "import logging",
            "log = logging.getLogger(__name__)",
            "log.debug('loading module %r' % __name__)",
            "# We want to write the librrPropagator here",
            "class librrPropagator(WESTPropagator):",
            "    def __init__(self, rc=None):",
            "        super(librrPropagator,self).__init__(rc)",
            "        # Get the rc file stuff",
            "        config = self.rc.config",
            "        for key in [('west','librr','init','model_file'),",
            "                    ('west','librr','init','init_time_step'),",
            "                    ('west','librr','init','final_time_step'),",
            "                    ('west','librr','init','num_time_step'),",
            "                    ('west','librr','data','pcoords')]:",
            "            config.require(key)",
            "        self.runner_config = {}",
            "        self.runner_config['model_file'] = config['west','librr','init','model_file']",
            "        self.runner_config['init_ts'] = config['west','librr','init','init_time_step']",
            "        self.runner_config['final_ts'] = config['west','librr','init','final_time_step']",
            "        self.runner_config['num_ts'] = config['west','librr','init','num_time_step']",
            "        self.runner_config['pcoord_keys'] = config['west','librr','data','pcoords']",
            "        # Initialize the libRR propagator using the init file",
            "        # Note: We COULD use a string, meaning we can save that to the ",
            "        # h5file and just pull the string out? I should look into this",
            "        self.runner = librr.RoadRunner(self.runner_config['model_file'])",
            "        self.runner.setIntegrator('gillespie')",
            "        self.runner.setIntegratorSetting('gillespie', 'variable_step_size', False)",
            "        self.runner.setIntegratorSetting('gillespie', 'nonnegative', True)",
            "        self.initial_pcoord = self.get_initial_pcoords()",
            "        self.full_state_keys = self.get_full_state_keys()",
            "        # setting time course so our result is just pcoord result",
            "        self.runner.timeCourseSelections = self.runner_config['pcoord_keys']",
            "    # Overwriting inhereted methods",
            "    def get_pcoord(self, state):",
            "        state.pcoord = copy.copy(self.initial_pcoord)",
            "        return",
            "    def gen_istate(self, basis_state, initial_state):",
            "        initial_state.pcoord = self.get_initial_pcoords()",
            "        return initial_state",
            "    # Rest is original class methods, except for propagate ofc",
            "    def get_initial_pcoords(self):",
            "        return [self.runner[x] for x in self.runner_config['pcoord_keys']]",
            "    def get_full_state_keys(self):",
            "        # TODO: Is this the best way? More importantly, is this the correct way?",
            "        # since RR timecourses are just concs and not the values themselves,",
            "        # we probably have to find a way to pull everything that are not constants",
            "        fs = self.runner.getFloatingSpeciesAmountsNamedArray().colnames",
            "        concs = ['['+x+']' for x in fs]",
            "        return fs+concs",
            "    def get_final_state(self):",
            "        # gets the final state info in full to be used by set_concs later",
            "        return [self.runner[x] for x in self.full_state_keys]",
            "    def set_runner_state(self, state):",
            "        if all(x == -1 for x in state):",
            "            self.runner.resetAll()",
            "        else:",
            "            for ival, val in enumerate(state):",
            "                self.runner.setValue(self.full_state_keys[ival], val)",
            "    def propagate(self, segments):",
            "        # Set some init states for segments",
            "        for iseg, segment in enumerate(segments):",
            "            piter = segment.n_iter-1",
            "            starttime = time.time()",
            "            seed = random.randint(0,2**14)",
            "            # Make sure we are reset so we can set the init state by hand",
            "            self.runner.resetAll()",
            "            # Set a new seed",
            "            self.runner.setIntegratorSetting('gillespie', 'seed', seed)",
            "            # Deal with init state here",
            "            # if segment.initpoint_type == Segment.SEG_INITPOINT_CONTINUES:",
            "            #     pass",
            "            # elif segment.initpoint_type == Segment.SEG_INITPOINT_NEWTRAJ:",
            "            #     pass",
            "            if piter > 0:",
            "                self.set_runner_state(segment.data['restart_state'])",
            "            # now we simulate using given parameters",
            "            result = self.runner.simulate(self.runner_config['init_ts'], ",
            "                                        self.runner_config['final_ts'],",
            "                                        self.runner_config['num_ts'])",
            "            # We need to store the current state of everything in the system",
            "            # so we can set it ",
            "            segment.data['final_state'] = self.get_final_state()",
            "            segment.data['seed'] = seed",
            "            # Get segment pcoords",
            "            segment.pcoord = result",
            "            # TODO: calc cputime somehow",
            "            segment.walltime = time.time() - starttime",
            "            segment.cputime = 0",
            "            segment.status = segment.SEG_STATUS_COMPLETE",
            "        return segments"
        ]
        full_text = "\n".join(lines)
        with open("libRR_propagator.py", "w") as f:
            f.write(full_text)

    def _write_restartDriver(self):
        lines = [
            "from __future__ import division; __metaclass__ = type",
            "import logging",
            "log = logging.getLogger(__name__)",
            "class RestartDriver(object):",
            "    def __init__(self, sim_manager, plugin_config):",
            "        super(RestartDriver, self).__init__()",
            "        if not sim_manager.work_manager.is_master:",
            "                return",
            "        self.sim_manager = sim_manager",
            "        self.data_manager = sim_manager.data_manager",
            "        self.system = sim_manager.system",
            "        self.priority = plugin_config.get('priority', 0)",
            "        # Register callback",
            "        sim_manager.register_callback(sim_manager.pre_propagation, self.pre_propagation, self.priority)",
            "    def pre_propagation(self):",
            "        segments = self.sim_manager.incomplete_segments.values()",
            "        n_iter = self.sim_manager.n_iter",
            "        if n_iter == 1:",
            "            return",
            "        parent_iter_group = self.data_manager.get_iter_group(n_iter - 1)",
            "        # Get parent ids for segments",
            "        parent_ids = [seg.parent_id for seg in segments]",
            "        # Get a list of unique parent ids and collect restart data for each",
            "        unique_parent_ids = set(parent_ids)",
            "        restart_data = {segid: {} for segid in unique_parent_ids}",
            "        try:",
            "            dsinfo = self.data_manager.dataset_options['final_state']",
            "        except KeyError:",
            "            raise KeyError('Data set final_state not found')",
            "        ds = parent_iter_group[dsinfo['h5path']]",
            "        for seg_id in unique_parent_ids:",
            "            if seg_id >= 0:",
            "                restart_data[seg_id]['final_state'] = ds[seg_id]",
            "            else:",
            "                restart_data[seg_id]['final_state'] = [-1] * ds[0].shape[0]",
            "        for segment in segments:",
            "            segment.data['restart_state'] = restart_data[segment.parent_id]['final_state']",
        ]
        full_text = "\n".join(lines)
        with open("restart_plugin.py", "w") as f:
            f.write(full_text)

    def _write_runsh(self):
        """
        write the run.sh file for WESTPA simulations
        """
        # TODO: Add submission scripts for varied clusters
        # TODO: Add a hook to write any submission scripts?
        lines = ["#!/bin/bash", 'w_run --work-manager processes "$@"']

        full_text = "\n".join(lines)
        with open("run.sh", "w") as f:
            f.write(full_text)
        os.chmod("run.sh", 0o764)

    def _write_envsh(self):
        """
        environment script that uses westpa.sh to setup the environment
        """
        if self.WESTPA_path is None:
            sys.exit("WESTPA path is not specified")

        lines = [
            "#!/bin/sh",
            'export WEST_SIM_ROOT="$PWD"',
            "export SIM_NAME=$(basename $WEST_SIM_ROOT)",
        ]

        if self.copy_run_net:
            lines.append('export RunNet="$WEST_SIM_ROOT/bngl_conf/run_network"')
        else:
            lines.append('export RunNet="{}/bin/run_network"'.format(self.bng_path))

        full_text = "\n".join(lines)
        with open("env.sh", "w") as f:
            f.write(full_text)
        os.chmod("env.sh", 0o764)

    def _write_auxfuncs(self):
        """
        auxilliary function, by default we want to avoid the first point because that's
        time in BNG output
        """
        lines = [
            "#!/usr/bin/env python",
            "import numpy",
            "def pcoord_loader(fieldname, coord_filename, segment, single_point=False):",
            "    pcoord    = numpy.loadtxt(coord_filename, dtype = numpy.float32)",
            "    if not single_point:",
            "        segment.pcoord = pcoord[:,1:]",
            "    else:",
            "        segment.pcoord = pcoord[1:]",
        ]

        full_text = "\n".join(lines)
        with open("aux_functions.py", "w") as f:
            f.write(full_text)

    def _write_bstatestxt(self):
        """
        a simple version of the basis states file,
        here you can define multiple starting points if you wanted
        """
        lines = ["0 1 0.net"]

        f = open("bstates/bstates.txt", "w")
        f.writelines(lines)
        f.close()

    def _write_getpcoord(self):
        """
        the pcoord acquiring script for the inital center
        """
        lines = [
            "#!/bin/bash\n",
            'if [ -n "$SEG_DEBUG" ] ; then',
            "  set -x",
            "  env | sort",
            "fi",
            "cd $WEST_SIM_ROOT",
            "cat bngl_conf/init.gdat > $WEST_PCOORD_RETURN",
            'if [ -n "$SEG_DEBUG" ] ; then',
            "  head -v $WEST_PCOORD_RETURN",
            "fi",
        ]

        full_text = "\n".join(lines)
        with open("westpa_scripts/get_pcoord.sh", "w") as f:
            f.write(full_text)
        os.chmod("westpa_scripts/get_pcoord.sh", 0o764)

    def _write_postiter(self):
        """
        a basic post-iteration script that deletes iterations that are
        older than 3 iterations
        """
        lines = [
            "#!/bin/bash",
            'if [ -n "$SEG_DEBUG" ] ; then',
            "    set -x",
            "    env | sort",
            "fi",
            "cd $WEST_SIM_ROOT || exit 1",
            "if [[ $WEST_CURRENT_ITER -gt 3 ]];then",
            '  PREV_ITER=$(printf "%06d" $((WEST_CURRENT_ITER-3)))',
            "  rm -rf ${WEST_SIM_ROOT}/traj_segs/${PREV_ITER}",
            "  rm -f  seg_logs/${PREV_ITER}-*.log",
            "fi",
        ]

        full_text = "\n".join(lines)
        with open("westpa_scripts/post_iter.sh", "w") as f:
            f.write(full_text)
        os.chmod("westpa_scripts/post_iter.sh", 0o764)

    def _write_initsh(self, traj=True):
        """
        WESTPA initialization script
        """
        if traj:
            lines = [
                "#!/bin/bash",
                "source env.sh",
                "rm -rf traj_segs seg_logs istates west.h5 ",
                "mkdir   seg_logs traj_segs",
                "cp $WEST_SIM_ROOT/bngl_conf/init.net bstates/0.net",
                'BSTATE_ARGS="--bstate-file bstates/bstates.txt"',
                'w_init $BSTATE_ARGS --segs-per-state {} --work-manager=threads "$@"'.format(
                    self.traj_per_bin
                ),
            ]
        else:
            lines = [
                "#!/bin/bash",
                "source env.sh",
                "rm -rf istates west.h5",
                "cp $WEST_SIM_ROOT/bngl_conf/init.net bstates/0.net",
                'BSTATE_ARGS="--bstate-file bstates/bstates.txt"',
                'w_init $BSTATE_ARGS --segs-per-state {} --work-manager=threads "$@"'.format(
                    self.traj_per_bin
                ),
            ]

        full_text = "\n".join(lines)
        with open("init.sh", "w") as f:
            f.write(full_text)
        os.chmod("init.sh", 0o764)

    def _write_systempy(self):
        """
        the system.py where the bin mapper is defined, most binning options
        go here
        """
        start_lines = [
            "from __future__ import division, print_function; __metaclass__ = type",
            "import numpy as np",
            "import westpa",
            "from westpa import WESTSystem",
            "from westpa.core.binning import VoronoiBinMapper",
            "from scipy.spatial.distance import cdist",
            "import logging",
            "from itertools import product",
            "log = logging.getLogger(__name__)",
            "log.debug('loading module %r' % __name__)",
            "def dfunc(p, centers):",
            "    ds = cdist(np.array([p]),centers)",
            "    return np.array(ds[0], dtype=p.dtype)",
            "class System(WESTSystem):",
            "    def initialize(self):",
            "        self.pcoord_ndim = {}".format(self.dims),
            "        self.pcoord_len = {}".format(self.plen + 1)
        ]
        end_lines = [
            "        self.bin_mapper = VoronoiBinMapper(dfunc, centers)",
            "        self.bin_target_counts = np.empty((self.bin_mapper.nbins,), int)",
            "        self.bin_target_counts[...] = {}".format(self.traj_per_bin),
        ]
        if self.binning_style == 'adaptive':
            bin_lines = [
                "        self.nbins = 1",
                "        centers = np.zeros((self.nbins,self.pcoord_ndim),dtype=np.float32)",
                "        i = np.loadtxt('bngl_conf/init.gdat')",
                "        centers[0] = i[0,1:]"
            ]
        else:
            bin_lines = [
                "        centers = []",
                f"        for center in product({','.join([f'dim{dim}_points' for dim in range(self.dims)])}):",
                "           centers.append(np.array(center))"
                ]
            for dim in range(self.dims):
                first_edge = self.first_edge[dim]
                last_edge = self.last_edge[dim]
                num_bins = self.num_bins[dim]
                step_size = (last_edge - first_edge) / num_bins
                first_center = first_edge + step_size / 2
                last_center = last_edge - step_size / 2
                bin_lines.insert(0,f"        dim{dim}_points = np.linspace({first_center},{last_center},{num_bins})")
        full_text = "\n".join(["\n".join(start_lines),"\n".join(bin_lines),"\n".join(end_lines)])
        with open("system.py", "w") as f:
            f.write(full_text)

    def _write_westcfg(self):
        """
        the WESTPA configuration file, another YAML file
        """
        # TODO: Expose max wallclock time?
        if self.propagator_type == "executable":
            self._executable_westcfg()
        elif self.propagator_type == "libRoadRunner":
            self._libRR_westcfg()

    def _libRR_westcfg(self):
        step_len = self.tau / self.plen
        step_no = self.plen

        if self.binning_style == 'adaptive':
            insert = [
                "    - plugin: westpa.westext.adaptvoronoi.AdaptiveVoronoiDriver",
                "      av_enabled: true",
                "      dfunc_method: system.dfunc",
                "      walk_count: {}".format(self.traj_per_bin),
                "      max_centers: {}".format(self.max_centers),
                "      center_freq: {}".format(self.center_freq),
            ]
        else:
            insert = []

        lines = [
            "# vi: set filetype=yaml :",
            "---",
            "west:",
            "  system:",
            "    driver: system.System",
            "    module_path: $WEST_SIM_ROOT",
            "  propagation:",
            "    max_total_iterations: {}".format(self.max_iter),
            "    max_run_wallclock:    72:00:00",
            "    propagator:           libRR_propagator.librrPropagator ",
            "    gen_istates:          false",
            "    block_size:           {}".format(self.block_size),
            "  data:\n",
            "    west_data_file: west.h5",
            "    datasets:",
            "      - name:        pcoord",
            "        scaleoffset: 4",
            "      - name:        seed",
            "        scaleoffset: 4",
            "      - name:        final_state",
            "        scaleoffset: 4",
            "  plugins:\n"] + insert + ["    - plugin: restart_plugin.RestartDriver",
            "  librr:",
            "    init:",
            "      model_file: {} # Generate this".format(
                os.path.join(self.main_dir, self.fname, "bngl_conf", "init.xml")
            ),
            "      init_time_step: 0",
            "      final_time_step: {}".format(self.tau),
            "      num_time_step: {}".format(step_no + 1),
            "    data:",
            "      pcoords: {}".format(('["' + '","'.join(self.pcoord_list) + '"]')),
        ]  # TODO: Write pcoords

        full_text = "\n".join(lines)
        with open("west.cfg", "w") as f:
            f.write(full_text)

    def _executable_westcfg(self):
        if self.binning_style == 'adaptive':
            insert = [
                "    - plugin: westpa.westext.adaptvoronoi.AdaptiveVoronoiDriver",
                "      av_enabled: true",
                "      dfunc_method: system.dfunc",
                "      walk_count: {}".format(self.traj_per_bin),
                "      max_centers: {}".format(self.max_centers),
                "      center_freq: {}".format(self.center_freq),
            ]
        else:
            insert = []

        lines = [
            "# vi: set filetype=yaml :",
            "---",
            "west:",
            "  system:",
            "    driver: system.System",
            "    module_path: $WEST_SIM_ROOT",
            "  propagation:",
            "    max_total_iterations: {}".format(self.max_iter),
            "    max_run_wallclock:    72:00:00",
            "    propagator:           executable",
            "    gen_istates:          false",
            "    block_size:           {}".format(self.block_size),
            "  data:",
            "    west_data_file: west.h5",
            "    datasets:",
            "      - name:        pcoord",
            "        scaleoffset: 4",
            "    data_refs:\n",
            "      segment:       $WEST_SIM_ROOT/traj_segs/{segment.n_iter:06d}/{segment.seg_id:06d}",
            "      basis_state:   $WEST_SIM_ROOT/bstates/{basis_state.auxref}",
            "      initial_state: $WEST_SIM_ROOT/istates/{initial_state.iter_created}/{initial_state.state_id}.rst",
            "  plugins:\n"] + insert + ["  executable:",
            "    environ:",
            "      PROPAGATION_DEBUG: 1",
            "    datasets:",
            "      - name:    pcoord",
            "        loader:  aux_functions.pcoord_loader",
            "        enabled: true",
            "    propagator:",
            "      executable: $WEST_SIM_ROOT/westpa_scripts/runseg.sh",
            "      stdout:     $WEST_SIM_ROOT/seg_logs/{segment.n_iter:06d}-{segment.seg_id:06d}.log",
            "      stderr:     stdout",
            "      stdin:      null",
            "      cwd:        null",
            "      environ:",
            "        SEG_DEBUG: 1",
            "    get_pcoord:",
            "      executable: $WEST_SIM_ROOT/westpa_scripts/get_pcoord.sh",
            "      stdout:     /dev/null ",
            "      stderr:     stdout",
            "    gen_istate:",
            "      executable: $WEST_SIM_ROOT/westpa_scripts/gen_istate.sh",
            "      stdout:     /dev/null",
            "      stderr:     stdout",
            "    post_iteration:",
            "      enabled:    true",
            "      executable: $WEST_SIM_ROOT/westpa_scripts/post_iter.sh",
            "      stderr:     stdout",
            "    pre_iteration:",
            "      enabled:    false",
            "      executable: $WEST_SIM_ROOT/westpa_scripts/pre_iter.sh",
            "      stderr:     stdout",
        ]

        full_text = "\n".join(lines)
        with open("west.cfg", "w") as f:
            f.write(full_text)

    def _write_runsegsh(self):
        """
        the most important script that extends an individual segment,
        this is where tau is defined
        """

        step_len = self.tau / self.plen
        step_no = self.plen

        lines = [
            "#!/bin/bash\n",
            'if [ -n "$SEG_DEBUG" ] ; then',
            "  set -x",
            "  env | sort",
            "fi",
            "if [[ -n $SCRATCH ]];then",
            "  mkdir -pv $WEST_CURRENT_SEG_DATA_REF",
            "  mkdir -pv ${SCRATCH}/$WEST_CURRENT_SEG_DATA_REF",
            "  cd ${SCRATCH}/$WEST_CURRENT_SEG_DATA_REF",
            "else",
            "  mkdir -pv $WEST_CURRENT_SEG_DATA_REF",
            "  cd $WEST_CURRENT_SEG_DATA_REF",
            "fi",
            'if [ "$WEST_CURRENT_SEG_INITPOINT_TYPE" = "SEG_INITPOINT_CONTINUES" ]; then',
            "  if [[ -n $SCRATCH ]];then",
            "    cp $WEST_PARENT_DATA_REF/seg_end.net ./parent.net",
            "    cp $WEST_PARENT_DATA_REF/seg.gdat ./parent.gdat",
            "  else",
            "    ln -sv $WEST_PARENT_DATA_REF/seg_end.net ./parent.net",
            "    ln -sv $WEST_PARENT_DATA_REF/seg.gdat ./parent.gdat",
            "  fi",
            "  $RunNet -o ./seg -p ssa -h $WEST_RAND16 --cdat 0 --fdat 0 -x -e -g ./parent.net ./parent.net {} {}".format(
                step_len, step_no
            ),
            "  tail -n 1 parent.gdat > $WEST_PCOORD_RETURN",
            "  cat seg.gdat >> $WEST_PCOORD_RETURN",
            'elif [ "$WEST_CURRENT_SEG_INITPOINT_TYPE" = "SEG_INITPOINT_NEWTRAJ" ]; then',
            "  if [[ -n $SCRATCH ]];then",
            "    cp $WEST_PARENT_DATA_REF ./parent.net",
            "  else",
            "    ln -sv $WEST_PARENT_DATA_REF ./parent.net",
            "  fi",
            "  $RunNet -o ./seg -p ssa -h $WEST_RAND16 --cdat 0 --fdat 0 -e -g ./parent.net ./parent.net {} {}".format(
                step_len, step_no
            ),
            "  cat seg.gdat > $WEST_PCOORD_RETURN",
            "fi",
            "if [[ -n $SCRATCH ]];then",
            "  cp ${SCRATCH}/$WEST_CURRENT_SEG_DATA_REF/seg_end.net $WEST_CURRENT_SEG_DATA_REF/.",
            "  rm -rf ${SCRATCH}/$WEST_CURRENT_SEG_DATA_REF",
            "fi"
        ]
        full_text = "\n".join(lines)
        with open("westpa_scripts/runseg.sh", "w") as f:
            f.write(full_text)
        os.chmod("westpa_scripts/runseg.sh", 0o764)

    def write_dynamic_files(self):
        """
        these files change depending on the given options, in particular
        sampling and binning options
        """
        self._write_systempy()
        self._write_westcfg()
        if self.propagator_type == "executable":
            self._write_runsegsh()
            self._write_initsh(traj=True)
        else:
            self._write_initsh(traj=False)

    def write_static_files(self):
        """
        these files are always (mostly) the same regardless of given options
        """
        # everything here assumes we are in the right folder
        self._write_envsh()
        self._write_bstatestxt()
        self._write_auxfuncs()
        self._write_runsh()
        if self.propagator_type == "executable":
            self._write_getpcoord()
            self._write_postiter()
        elif self.propagator_type == "libRoadRunner":
            self._write_restartDriver()
            self._write_librrPropagator()

    def make_sim_folders(self):
        """
        make folders WESTPA needs
        """
        self.sim_dir = self.fname
        try:
            os.makedirs(self.fname)
        except FileExistsError as e:
            # TODO: make an overwrite option
            print(f"The folder {self.fname} you are trying to create already exists")
            print(e)
        os.chdir(self.fname)
        os.makedirs("bngl_conf")
        os.makedirs("bstates")
        if self.propagator_type == "executable":
            os.makedirs("westpa_scripts")

    def copy_run_network(self):
        """
        this copies the run_network binary with correct permissions to where
        WESTPA will expect to find it.
        """
        # Assumes path is absolute path and not relative
        shutil.copyfile(
            os.path.join(self.bng_path, "bin/run_network"), "bngl_conf/run_network"
        )
        os.chmod("bngl_conf/run_network", 0o764)

    def run_BNGL_on_file(self):
        """
        this function runs the BNG2.pl on the given bngl file
        to get a) .net file for the starting point and b) .gdat file
        to get the first voronoi center for the simulation
        """
        if self.propagator_type == "executable":
            self._executable_BNGL_on_file()
        elif self.propagator_type == "libRoadRunner":
            self._libRR_BNGL_on_file()

    def _libRR_BNGL_on_file(self):
        # We still need this stuff
        model = self._executable_BNGL_on_file()
        # But we also need to generate the XML file
        # get in the conf folder
        os.chdir("bngl_conf")
        # make a copy that we will use to generate the XML
        sim = model.setup_simulator()
        sbml_str = sim.getCurrentSBML()
        with open("init.xml", "w") as f:
            f.write(str(sbml_str))
        os.chdir(os.path.join(self.main_dir, self.sim_dir))

    def _executable_BNGL_on_file(self):
        # IMPORTANT!
        # This assumes that the bngl file doesn't have any directives at the end!
        # we have a bngl file
        os.chdir("bngl_conf")
        # Make specific BNGL files for a) generating network and then
        # b) getting a starting  gdat file
        model = bionetgen.bngmodel(self.bngl_file)
        model.add_action("generate_network", action_args={"overwrite": 1})
        model.add_action(
            "simulate", action_args={"method": "'ssa'", "t_end": 2, "n_steps": 2}
        )
        with open("init.bngl", "w") as f:
            f.write(str(model))
        r = bionetgen.run("init.bngl", "for_init")
        shutil.copyfile(os.path.join("for_init", "init.net"), "init.net")
        header_str = ""
        for i in r[0].dtype.names:
            header_str += " " + i
        np.savetxt("init.gdat", r[0], header=header_str)
        shutil.rmtree("for_init")
        os.chdir(os.path.join(self.main_dir, self.sim_dir))
        return model

    def run(self):
        """
        runs the class functions in appropriate order to
        make the WESTPA simultion folder
        """
        self.make_sim_folders()
        if self.copy_run_net:
            self.copy_run_network()
        self.write_static_files()
        self.run_BNGL_on_file()
        self.write_dynamic_files()
        return
