#!/usr/bin/env python3

import argparse, os, random, subprocess, logging
from colorama import Fore, Style, init
from tabulate import tabulate
from string import Template

# Initialize colorama for colored output
init(autoreset=True)

# Abbreviations for colors
G = Fore.GREEN
R = Fore.RED
Y = Fore.YELLOW
B = Fore.BLUE
M = Fore.MAGENTA
C = Fore.CYAN
RE = Style.RESET_ALL

# Default queue
LSF_QUEUE = "normal"

# Shell script template
SCRIPT_TEMPLATE = Template("""#!/bin/bash

#BSUB -J $input
#BSUB -n $ntasks
#BSUB -R "select[mem>$mem]rusage[mem=$mem]"
#BSUB -W $time
#BSUB -o $pog_dir/%J.out
#BSUB -e $pog_dir/%J.err
#BSUB -q $queue

cd $pog_dir

echo
echo Launching FLUKA run...
$fluka_command $pog_dir/$input
""")

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

### Function to generate input file with a random seed ###
def generate_input(input, iteration):
    seed = random.randint(1, int(9E7))
    new_randomiz = f"RANDOMIZ          1.{seed:>10n}\n"

    with open(f"{input}.inp", "r+") as f:
        data = f.readlines()
        for index, line in enumerate(data):
            if "RANDOMIZ" in line:
                data[index] = new_randomiz
                break
        f.seek(0)
        f.writelines(data)
        f.truncate()

    file_name = f"{input}_{iteration:04d}.inp"
    os.rename(f"{input}.inp", file_name)
    return file_name

### Function to generate the shell script for each job ###
def generate_sh(input, iteration, fluka_path, custom_exe, mem, ntasks, time):
    pog_dir = os.getcwd()
    fluka_command = f"{fluka_path}/rfluka -M 1" if custom_exe == "None" else f"{fluka_path}/rfluka -M 1 -e {custom_exe}"
    
    script_content = SCRIPT_TEMPLATE.substitute(
        input=input,
        fluka_command=fluka_command,
        pog_dir=pog_dir,
        mem=mem,
        ntasks=ntasks,
        time=time
    )
    script_name = f"job_{iteration:04d}.sh"
    
    with open(script_name, "w") as sh:
        sh.write(script_content)
    os.chmod(script_name, 0o755)

### Function to launch jobs ###
def launch_jobs(input_file, job_number, custom_exe, queue, mem, ntasks, time, dry_run, output_dir):
    stripped_name = os.path.splitext(os.path.basename(input_file))[0]
    base_directory_name = stripped_name if output_dir is None else output_dir
    new_directory_name = base_directory_name
    counter = 1
    
    while os.path.exists(new_directory_name):
        new_directory_name = f"{base_directory_name}_{counter}"
        counter += 1
    
    directory = new_directory_name
    os.makedirs(directory)
    
    for i in range(1, job_number + 1):
        job_name = f"job_{i:04d}"
        job_dir = os.path.join(directory, job_name)
        os.makedirs(job_dir)
        os.system(f"cp {input_file} {job_dir}")
        
        os.chdir(job_dir)
        new_input = generate_input(stripped_name, i)
        generate_sh(new_input, i, FLUKA_PATH, custom_exe, mem, ntasks, time)

        if dry_run:
            logging.info(f"Dry run: bsub < ./{job_name}.sh")
        else:
            result = subprocess.run(f"bsub < ./{job_name}.sh", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Job {job_number} {result.stdout.strip()}")
            else:
                print(f"Job {job_number} submission failed: {result.stderr.strip()}")
        
        os.chdir("../..")

### Main script execution ###
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Launch FLUKA jobs on LSF',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example usage:\n ./launch_jobs_lsf.py -f input.inp -n 10 -c custom_exe -q queue -m 1500 -t 1 -T 1-00:00:00")
    
    parser.add_argument('-f', '--input', type=str, required=True, help="Input file name for FLUKA (must end with .inp)")
    parser.add_argument('-n', '--njobs', type=int, required=True, help='Number of jobs to run')
    parser.add_argument('-c', '--custom_exe', type=str, default="None", help='Path to the custom executable')
    parser.add_argument('-q', '--queue', type=str, default=LSF_QUEUE, help='Queue to submit jobs to')
    parser.add_argument('-m', '--mem', type=str, default="1500", help='Memory allocation for the job')
    parser.add_argument('-t', '--ntasks', type=int, default=1, help='Number of tasks for the job')
    parser.add_argument('-T', '--time', type=str, default="1-00:00:00", help='Time limit for the job (default: 1-00:00:00, max: 4-00:00:00)')
    parser.add_argument('-w', '--dry-run', action='store_true', help='Perform a dry run without submitting jobs')
    parser.add_argument('-d','--output-dir', type=str, help='Output directory for job files')
    args = parser.parse_args()

    if not args.input.endswith(".inp"):
        logging.error(f"Input file must end with .inp")
        exit(1)

    try:
        FLUKA_PATH = subprocess.check_output(["fluka-config", "--bin"]).decode().strip()
        FLUKA_FOLDER = subprocess.check_output(["fluka-config", "--path"]).decode().strip()
    except subprocess.CalledProcessError:
        logging.error(f"FLUKA is not installed or fluka-config command is not found.")
        exit(1)

    # Validate time limit
    max_time = "4-00:00:00"
    if args.time > max_time:
        logging.error(f"Time limit cannot exceed {max_time}")
        exit(1)
    
    table = [
        ["Command",  "Parameter",                    "Value"],
        ["-f",      f"{R}Input file{RE}",           f"{M}{args.input}{RE}"],
        ["-n",      f"{R}Number of jobs{RE}",       f"{M}{args.njobs}{RE}"],
        ["-c",      f"{M}Custom executable{RE}",    f"{M}{args.custom_exe}{RE}"],
        ["-q",      f"{M}Queue{RE}",                f"{M}{args.queue}{RE}"],
        ["-m",      f"{C}Memory{RE}",               f"{C}{args.mem}{RE}"],
        ["-t",      f"{C}Number of tasks{RE}",      f"{C}{args.ntasks}{RE}"],
        ["-T",      f"{C}Time limit{RE}",           f"{C}{args.time}{RE}"],
        [" ",       f"{B}FLUKA Path{RE}",           f"{B}{FLUKA_PATH}{RE}"],
        [" ",       f"{B}FLUKA Folder{RE}",         f"{B}{FLUKA_FOLDER}{RE}"],
        ["-d",      f"{B}Output Directory{RE}",     f"{B}{args.output_dir if args.output_dir else 'Default'}{RE}"],
        ["-w",      f"{Y}Dry Run{RE}",              f"{Y}{args.dry_run}{RE}"]
    ]
    print(tabulate(table, headers="firstrow", tablefmt="simple_outline"))

    confirmation = input("Proceed with launching jobs? (yes/no): ")
    if confirmation.lower() not in ['yes', 'y']:
        logging.info(f"{R}Aborting job launch.{RE}")
        exit()

    launch_jobs(args.input, args.njobs, args.custom_exe, args.queue, args.mem, args.ntasks, args.time, args.dry_run, args.output_dir)
