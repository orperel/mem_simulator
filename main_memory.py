from mem_ifc import MemoryInterface
from math import ceil
from math import log2


class MainMemory(MemoryInterface):
    """
    The main memory of the system.
    Assumption: No Disk drive is attached beyond this level
    (all data must be present at this level in this simulation).
    """

    # Main memory parameters defined here
    MAIN_MEM_SIZE_IN_BYTES = 16 * 1024  # Mem capacity is 16MB # TODO: Change back to 16MB, too slow for debug
    MEM_BUS_WIDTH = 64                         # In bits
    MEM_ACCESS_TIME = 100                      # In clock cycles
    MEM_BUS_ACCESS_TIME = 1                    # Any additional transfer on bus after accessing for first entry

    # Main memory contents, initialized to 0 until input file is loaded
    mem = [0] * MAIN_MEM_SIZE_IN_BYTES

    def __init__(self, mem_input_file):
        """
        C'tor for Main Memory object, always initialized from a memory input file.
        :param mem_input_file: The initial contents of main memory. Memory will be padded with zeros if the
                               contents in this file are too short.
                               (assumption: file is valid, each line contains a single byte value for the
                               next sequential memory entry, starting from 0)
        """

        super(MainMemory, self).__init__(None)  # Call super constructor with no "next" memory (main mem is the last)
        cursor = 0  # Start writing to mem from address 0

        # Init main memory from input file
        with open(mem_input_file, 'r') as mem_in:
            for line in mem_in:
                entry = line.rstrip()
                self.mem[cursor] = int(entry, 16)
                cursor += 1

    def transfer_cycles(self, block_size: int) -> int:
        """
        Returns the amount of cycles needed to read / write the block_size given to the main memory.
        (this is the amount of times it takes to pass data on the bus between L1 cache and the previous level
        in the hierarchy).
        :param block_size: The amount of data passed on the bus, excluding address size
        :return: Amount of cycles taken to pass the data on the bus
        """
        # Access time is 100 clock cycles + 1 cc for each additional block transferred on the bus starting from the 2nd.
        address_size = int(log2(self.MAIN_MEM_SIZE_IN_BYTES))
        access_time = self.MEM_ACCESS_TIME + \
                      (ceil((block_size + address_size) / self.MEM_BUS_WIDTH) - 1) * self.MEM_BUS_ACCESS_TIME
        return access_time

    def is_address_present(self, address: int) -> bool:
        """
        We assume data is always present on the Main Memory level (don't account for page faults)
        """
        return True

    def read_miss_callback(self, address: int, block_size: int, data=[]) -> int:
        """
        Do nothing for main memory, data should always be present and no miss should occur.
        :return: (clock cycles elapsed as int)
        """
        return 0

    def write_miss_callback(self, address: int, block_size: int, data=[]) -> int:
        """
            Do nothing for main memory, no write miss should occur hee.
            :return: (clock cycles elapsed as int)
        """
        return 0

    def write(self, address: int, block_size: int, data=[]) -> int:
        """
        Save the block of data to the given address.
        :param address: Address to write to, 4 byte aligned
        :param block_size: Block size to write to memory, in amount of bytes
        :param data: Data to be saved, as a list of bytes, little endian format expected (will be saved as is)
        :return: (clock cycles elapsed as int)
        """

        # Store data in mem cells from "address" to "address+block_size".
        for i in range(0, block_size):
            self.mem[address + i] = data[i]

        access_time = self.transfer_cycles(block_size)
        return access_time

    def read(self, address: int, block_size: int) -> (list, int):
        """
        Perform read operation from the main memory, at the size of block_size.
        This method assumes the data is stored in the memory, and is valid.
        :param address: Address to read from, 4 byte aligned
        :param block_size: Block size to read from memory, in amount of bytes
        :return: (data read as list of bytes, clock cycles elapsed as int)
        """

        data = self.mem[address:address+block_size]
        access_time = self.transfer_cycles(block_size)

        return data, access_time

    def dump_memory(self, *file_names):
        """
        Dumps the contents of memory hierarchy to the file names given as argument.
        Each level may use one or two files, and pass the rest of the list to the next level.
        For example: (l1.txt, l2way0.txt, l2way1.txt, memout.txt), L1 will use l1.txt and pass
        (l2way0.txt, l2way1.txt, memout.txt) to L2 cache, which passes (memout.txt) to MainMemory.
        The format used in each file is byte-per-line, no headers or footers.
        :param file_names: A list of file names to be used as output for this point in the hierarchy and those
                           beyond it.
        """
        file_name = file_names[0]
        self.dump_output_file(file_name, self.mem)

    def print_mem(self, limit=-1):
        """Prints the contents of the main memory to the console, for debugging and logging purposes.
           limit args allows to print only first "limit" lines to avoid bloating the console."""
        cursor = 0
        print("Main memory:")

        for entry in self.mem:
            if cursor % 4 == 0:
                print('\n0x' + str(cursor).zfill(6) + ' ', end="")
            print(hex(entry)[2:] + ' ', end="")
            cursor += 1
            if cursor == limit:
                break
