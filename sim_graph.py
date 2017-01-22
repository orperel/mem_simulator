import traceback
import matplotlib.pyplot as plt
from sim import run_sim


def plot(x_vals, y_vals, title, x_axis, y_axis, x_ticks, y_ticks):

    plt.plot(x_vals, y_vals)
    plt.xlabel(x_axis)
    plt.ylabel(y_axis)
    plt.title(title)
    plt.xticks(x_vals, x_ticks, rotation='vertical')
    plt.yticks(y_vals, y_ticks, rotation='horizontal')
    plt.grid(True)
    plt.savefig(title + ".png")
    plt.show()


def plot_by_l2_block(block_start, block_end, block_l1):

    mode = 2

    block_l2 = block_start
    x_vals = []
    y_vals = []

    while block_l2 <= block_end:
        l1_miss_rate, cycles_elapsed, amat =\
            run_sim(mode, block_l1, block_l2, 'trace.txt', 'memin.txt', 'memout.txt', 'l1.txt',
                'l2way0.txt', 'l2way1.txt', 'stats.txt')

        x_vals.append(block_l2)
        y_vals.append(amat)

        block_l2 *= 2

    x_axis = 'L2 Block size'
    y_axis = 'Amat'
    x_ticks = [str(val) for val in x_vals]
    y_ticks = ["{0:.4f}".format(val) for val in y_vals]
    title = 'Amat as function of L2 Block size'
    plot(x_vals, y_vals, title, x_axis, y_axis, x_ticks, y_ticks)


def plot_by_l1_block(block_start, block_end, block_l2):

    mode = 1 if (block_l2 == 0) else 2

    block_l1 = block_start
    x_vals = []
    y_vals = []

    while block_l1 <= block_end:
        l1_miss_rate, cycles_elapsed, amat =\
            run_sim(mode, block_l1, block_l2, 'trace.txt', 'memin.txt', 'memout.txt', 'l1.txt',
                'l2way0.txt', 'l2way1.txt', 'stats.txt')

        x_vals.append(block_l1)
        y_vals.append(l1_miss_rate if (mode == 1) else cycles_elapsed)

        block_l1 *= 2

    x_axis = 'L1 Block size'
    y_axis = 'L1 Miss Rate' if (mode == 1) else 'Total Runtime (cycles)'
    x_ticks = [str(val) for val in x_vals]
    y_ticks = ["{0:.4f}".format(val) for val in y_vals] if (mode == 1) else [str(val) for val in y_vals]
    title = 'L1 Miss rate as function of L1 Block size' if (mode == 1) else 'Total runtime as function of L1 Block size'
    plot(x_vals, y_vals, title, x_axis, y_axis, x_ticks, y_ticks)


if __name__ == "__main__":
    """
    Main function for the memory hierarchy simulation.
    """
    try:
        plot_by_l1_block(4, 128, 0)
        plot_by_l1_block(4, 128, 128)
        plot_by_l2_block(8, 256, 8)
    except Exception as err:
        print("Simulation plotting ended with an error.")
        tb = traceback.format_exc()
        print(tb)
