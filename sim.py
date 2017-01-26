#!/usr/bin/python

import sys
import traceback

import sim_constants
from l1cache import L1Cache
from l2cache import L2Cache
from main_memory import MainMemory
from sim_constants import CPU_DATA_SIZE


"""
    This is the "main" file that runs the mem-cache simulator.
    Choose between L1 / L2 modes while simulating as stated in project's instructions.

    Assumptions:
    ------------
        -   When L2 cache is on, compulsory miss that goes as deep as the Main Memory will update L1 and L2 serially
            (the time calculated is transferring data on bus from Main memory to L2 + transferring data from L2 to L1).
        -   Dirty & Valid bit are not included within the address bits (meaning we have 24 address bits + 2 for status).
        -   All addresses are expected to be aligned to 4, and CPU is not expected to fetch non-aligned addresses.
        -   The offset bits include the 2 LSB of alignment bits.
            (This can easily be changed by subtracting 2 from the number of offset bits, see note in l1cache c'tor).
            Though we could optimize here, we chose to do so to stay on the same page with recitation 3 - Q 1.5.
        -   When block size is exactly the same size of the CPU word (e.g: both are 4 bytes), we don't optimize
            in case of a write miss: we still fetch the required block from L2 / Main memory even though it will
            completely get overridden (this is keep coherence with the general case of block size > 4).
        -   Python's representation of bytes is simply an alias of Strings.
            To keep things simple, memory is represented in integers by this simulator
            even though we mostly deal with bytes (we make sure to treat only the LSB of those integers, as bytes).
            The end result of the simulation is not affected, even though output file sizes may seem larger
            (each byte is wrapped in an integer where the 24 MSB are zeros and aren't used).
"""


def dump_statistics(l1_cache, l2_cache, stats, cycles_elapsed, mem_cycles_elapsed, mem_instructions_count) \
        -> (float, int, float):
    """
    Dumps the statistics of the simulation to the stats file
    :param l1_cache: L1 Cache object
    :param l2_cache: L2 Cache object
    :param stats: Stats file name, the output of this function
    :param cycles_elapsed: The number of clock cycles the whole simulation took
    :param mem_cycles_elapsed: The number of clock cycles memory operations took
    :param mem_instructions_count: The number of load / store instructions executed
    @:return Statistics relevant for plotting
    """

    # Open stats file for write
    with open(stats, 'w') as stats_out:

        # program running time in cycles
        stats_out.write(str(int(cycles_elapsed)) + "\n")

        # number of read hits in L1
        stats_out.write(str(int(l1_cache.read_hits)) + "\n")

        # number of write hits in L1
        stats_out.write(str(int(l1_cache.write_hits)) + "\n")

        # number of read misses in L1
        stats_out.write(str(int(l1_cache.read_misses)) + "\n")

        # number of write misses in L1
        stats_out.write(str(int(l1_cache.write_misses)) + "\n")

        if l2_cache is None:
            stats_out.write(str(0) + "\n")
            stats_out.write(str(0) + "\n")
            stats_out.write(str(0) + "\n")
            stats_out.write(str(0) + "\n")
        else:
            # number of read hits in L2
            stats_out.write(str(int(l2_cache.read_hits)) + "\n")

            # number or write hits in L2
            stats_out.write(str(int(l2_cache.write_hits)) + "\n")

            # number of read misses in L2
            stats_out.write(str(int(l2_cache.read_misses)) + "\n")

            # number of write misses in L2
            stats_out.write(str(int(l2_cache.write_misses)) + "\n")

        # L1 local miss rate
        l1_misses = l1_cache.read_misses + l1_cache.write_misses
        l1_hits = l1_cache.read_hits + l1_cache.write_hits
        if (l1_misses + l1_hits) > 0:
            l1_miss_rate = l1_misses / (l1_misses + l1_hits)
        else:
            l1_miss_rate = 0  # Protect against empty simulations
        stats_out.write("{0:.4f}".format(l1_miss_rate) + "\n")

        # global miss rate
        if l2_cache is None:
            # global miss rate for L1 only is L1 miss rate
            global_miss_rate = l1_miss_rate
        else:
            # global miss rate for L1 & L2 miss rate
            l2_misses = l2_cache.read_misses + l2_cache.write_misses
            l2_hits = l2_cache.read_hits + l2_cache.write_hits

            if (l2_misses + l2_hits) > 0:
                l2_miss_rate = l2_misses / (l2_misses + l2_hits)
                global_miss_rate = l1_miss_rate * l2_miss_rate
            else:
                global_miss_rate = 0  # Protect against empty simulations

        stats_out.write("{0:.4f}".format(global_miss_rate) + "\n")

        # AMAT
        amat = mem_cycles_elapsed / mem_instructions_count
        stats_out.write("{0:.4f}".format(amat))

        # Returns results relevant for plotting
        return l1_miss_rate, cycles_elapsed, amat


def dump_mem_hierarchy_to_files(mem_interface, levels, memout, l1, l2way0, l2way1):
    """
    Dumps the content of the memory hierarchy to the file names given as input.
    :param mem_interface: Pointer to first level in the memory hierarchy (should be a mem_ifc, usually L1 cache)
    :param levels: Number of levels of caches in the system (1 or 2 for L1 or L1&L2 respectively)
    :param memout: Name of main memory output file
    :param l1: Name of L1 cache output file
    :param l2way0: Name of L2 cache - way 0 output
    :param l2way1: Name of L2 cache - way 1 output
    """
    if levels == 1:
        mem_interface.dump_memory(l1, memout)  # Will chain to the entire hierarchy
    elif levels == 2:
        mem_interface.dump_memory(l1, l2way0, l2way1, memout)  # Will chain to the entire hierarchy


def big_endian_to_little_endian(data: int) -> list:
    """
    Converts input data from big endian format to little endian
    :param data: Data of 32 bit
    :return: The data converted to little endian, as a list of bytes
    """
    little_end_data = [0] * 4
    little_end_data[0] = data & 0x000000FF
    little_end_data[1] = (data & 0x0000FF00) >> 8
    little_end_data[2] = (data & 0x00FF0000) >> 16
    little_end_data[3] = (data & 0xFF000000) >> 24
    return little_end_data


def simulate_cpu(trace, mem_interface) -> int:
    """
    Simulates the functionality of the CPU according to the opcodes in the trace file.
    The CPU will access memory via the memory hierarchy, represented by mem_interface.
    :param trace: Input file, containing Store and Load commands for the CPU to execute
    :param mem_interface: Pointer tot he first memory level in the memory hierarchy, usually the L1 Cache.
                          Next memory levels will be referred indirectly by the hierarchy, when needed.
    :return: (Amount of clock cycles the entire simulation took,
              Amount of clock cycles only memory operations took,
              Amount of store / load instructions executed)
    """

    cc_counter = 0              # A counter for the total clock cycles the program took
    mem_cc_counter = 0          # A counter for the amount of clock cycles only memory operations took
    count_mem_instructions = 0  # A counter for the number of memory instructions executed

    # Perform instructions according to trace file
    with open(trace, 'r') as cpu_calls:
        for next_instruction in cpu_calls:

            next_instruction = next_instruction.rstrip()  # Remove redundant whitespaces
            inst_decode = next_instruction.split(sim_constants.FILE_DELIMITER)  # Decode instruction
            num_of_cycles_passed = int(inst_decode[0])  # First component is number of cycles elapsed for non L/S commands
            cc_counter += num_of_cycles_passed
            is_store_instruction = (inst_decode[1] == 'S')  # Second component defines (L)oad or (S)tore command
            address = int(inst_decode[2], 16)  # Third component is the address we're trying to access
            if is_store_instruction:
                data = int(inst_decode[3], 16)  # For store commands there is another, 4th component, for data we write
                data_little_end = big_endian_to_little_endian(data)  # Memory hierarchy stores data in little endian

                # Execute store instruction
                cycles_elapsed = mem_interface.store(address, CPU_DATA_SIZE, data_little_end)
            else:
                # Execute load instruction
                data_fetched, cycles_elapsed = mem_interface.load(address, CPU_DATA_SIZE)
            cc_counter += cycles_elapsed
            mem_cc_counter += cycles_elapsed
            count_mem_instructions += 1

    return cc_counter, mem_cc_counter, count_mem_instructions


def run_sim(levels, b1, b2, trace, memin, memout, l1, l2way0, l2way1, stats):
    """
    Runs a single iteration of the simulation of a CPU on the memory hierarchy.
    :param levels: Number of cache levels (1 or 2)
    :param b1: Size of blocks for L1 cache
    :param b2: Size of blocks for L2 cache (optional)
    :param trace: Trace file containing sequence of load / store commands for the CPU to execute
    :param memin: Initial state of the main memory in the beginning of the simulation.
    :param memout: Final state of the main memory in the end of the simulation.
    :param l1: Final state of the L1 cache in the end of the simulation.
    :param l2way0: Final state of the L2 cache - way 0 in the end of the simulation (optional)
    :param l2way1: Final state of the L2 cache - way 1 in the end of the simulation (optional)
    :param stats: Output file containing the statistics of the simulation by the end of the simulation
    """

    # Construct memory hierarchy
    main_mem = MainMemory(memin)
    l1_cache = None
    l2_cache = None

    # Choose L1 cache only or L1 & L2 caches
    if levels == 1:
        l1_cache = L1Cache(main_mem, b1)
    elif levels == 2:
        l2_cache = L2Cache(main_mem, b2)
        l1_cache = L1Cache(l2_cache, b1)
    else:
        print("Invalid levels argument")
        exit(1)

    # Memory hierarchy starts here, this is the first memory the CPU tries to access
    mem_hierarchy = l1_cache

    # This function drives the simulation of the cpu over the trace file, memory accesses will occur here
    cycles_elapsed, mem_cycles_elapsed, mem_instructions_count = simulate_cpu(trace, mem_hierarchy)

    # Dumps the state of the memory hierarchy components to the respective output file.
    dump_mem_hierarchy_to_files(mem_hierarchy, levels, memout, l1, l2way0, l2way1)

    # Dumps the statistics of the simulation to the output file
    # Returns statistics relevant for graph plotting
    l1_miss_rate, cycles_elapsed, amat = \
        dump_statistics(l1_cache, l2_cache, stats, cycles_elapsed, mem_cycles_elapsed, mem_instructions_count)
    
    print("Simulation ended successfully")

    return l1_miss_rate, cycles_elapsed, amat

if __name__ == "__main__":
    """
    Main function for the memory hierarchy simulation.
    """
    
    try:
        run_sim(int(sys.argv[1]),  # levels
                int(sys.argv[2]),  # b1
                int(sys.argv[3]),  # b2
                sys.argv[4],       # trace.txt
                sys.argv[5],       # memin.txt
                sys.argv[6],       # memout.txt
                sys.argv[7],       # l1.txt
                sys.argv[8],       # l2way0.txt
                sys.argv[9],       # l2way1.txt
                sys.argv[10])      # stats.txt
    except NotImplementedError as err:
        print("Simulation ended with an error.")
        tb = traceback.format_exc()
        print(tb)
    except Exception as err:
        print("Simulation ended with an error.")
        tb = traceback.format_exc()
        print(tb)
