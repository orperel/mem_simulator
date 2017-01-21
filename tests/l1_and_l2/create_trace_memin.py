import numpy as np

def inst_to_load_store(inst):
    if inst == 0:
        return "L"
    if inst == 1:
        return "S"


num_of_transctions = 10

other_opers = np.random.randint(0, 11, num_of_transctions)
insts = np.random.randint(0, 2, num_of_transctions)
addresses = np.random.randint(0, 1024*1024, num_of_transctions)
store_data = np.random.randint(0, 2**16, num_of_transctions)    # 2**32 is too high for int32
mem_data = np.random.randint(0, 256, num_of_transctions)

with open("trace.txt", 'w') as trace:
    for i in range(num_of_transctions):
        if insts[i] == 1:   # Store
            store = " " + str(hex(store_data[i])[2:]).upper().zfill(8)
        else:   # load
            store = ""
        trace.write(str(other_opers[i]) + " " + str(inst_to_load_store(insts[i]))\
                     + " " + str(hex(addresses[i])[2:]).upper().zfill(6) + store)
        if i != num_of_transctions - 1:
            trace.write("\n")

with open("memin.txt", 'w') as mem_in:
    for i in range(num_of_transctions):
        sorted_adds = np.sort(addresses)
        if i != 0:
            prev = sorted_adds[i-1]
        else:
            prev = -1
        for j in range(prev+1, sorted_adds[i]):
            mem_in.write("00\n")
        mem_in.write(str(hex(mem_data[i])[2:]).upper().zfill(2))
        if i != num_of_transctions - 1:
            mem_in.write("\n")

