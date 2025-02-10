#!/usr/bin/env python3

import argparse, os, random, subprocess, logging
import htcondor
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
HTCONDOR_QUEUE = "vanilla"

# Shell script template
SCRIPT_TEMPLATE = Template("""#!/bin/env bash

. /cvmfs/sft.cern.ch/lcg/views/setupViews.sh LCG_97python3 x86_64-centos7-gcc9-opt

$fluka_command $input
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
def generate_sh(input, iteration, fluka_path, custom_exe):
    
    fluka_command = f"{fluka_path}/rfluka -M 1" if custom_exe == "None" else f"{fluka_path}/rfluka -M 1 -e {custom_exe}"

    script_content = SCRIPT_TEMPLATE.substitute(
        fluka_command=fluka_command,
        input=input
    )
    script_name = f"job_{iteration:04d}.sh"
    
    with open(script_name, "w") as sh:
        sh.write(script_content)
    os.chmod(script_name, 0o755)
    
    return script_name

### Function to generate the submit description for each job ###
def generate_submit_description(iteration, input, script_name, mem, ncpu, disk, time, transfer_files, output, error, log):
    submit_description = {
        "universe": "vanilla",
        "executable": script_name,
        "transfer_input_files": input,
        "should_transfer_files": transfer_files,
        "when_to_transfer_output": "ON_EXIT",
        "output": output,
        "error": error,
        "log": log,
        "request_memory": mem,
        "request_cpus": ncpu,
        "request_disk": disk,
        "+MaxRuntime": time,
    }
    return submit_description

### Function to launch jobs ###
def launch_jobs(input_file, job_number, custom_exe, queue, mem, ncpu, disk, time, dry_run, output_dir, transfer_files, output, error, log):
    stripped_name = os.path.splitext(os.path.basename(input_file))[0]
    base_directory_name = stripped_name if output_dir is None else output_dir
    new_directory_name = base_directory_name
    counter = 1
    
    while os.path.exists(new_directory_name):
        new_directory_name = f"{base_directory_name}_{counter}"
        counter += 1
    
    directory = new_directory_name
    os.makedirs(directory)
    
    if not dry_run:
        schedd = htcondor.Schedd()
    
    for i in range(1, job_number + 1):
        job_name = f"job_{i:04d}"
        job_dir = os.path.join(directory, job_name)
        os.makedirs(job_dir)
        os.system(f"cp {input_file} {job_dir}")
        
        os.chdir(job_dir)
        new_input = generate_input(stripped_name, i)
        script_name = generate_sh(new_input, i, FLUKA_PATH, custom_exe)
        submit_description = generate_submit_description(i, new_input, script_name, mem, ncpu, disk, time, transfer_files, output, error, log)

        if dry_run:
            logging.info(f"Dry run: condor_submit {submit_description}")
        else:
            submit_result = schedd.submit(htcondor.Submit(submit_description))
            logging.info(f"Submitted job {submit_result.cluster()}")
        
        os.chdir("../..")

### Main script execution ###
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Launch FLUKA jobs on HTCondor',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Example usage:\n ./launch_jobs_htcondor.py -f input.inp -n 10 -c custom_exe -q queue -m 1500 -t 1 -o 1 -T 86400")
    
    parser.add_argument('-f', '--input', type=str, required=True, help="Input file name for FLUKA (must end with .inp)")
    parser.add_argument('-n', '--njobs', type=int, required=True, help='Number of jobs to run')
    parser.add_argument('-c', '--custom_exe', type=str, default="None", help='Path to the custom executable')
    parser.add_argument('-q', '--queue', type=str, default=HTCONDOR_QUEUE, help='Queue to submit jobs to')
    parser.add_argument('-m', '--mem', type=str, default="1500", help='Memory allocation for the job')
    parser.add_argument('-t', '--ncpu', type=int, default=1, help='Number of cpus for the job')
    parser.add_argument('-o', '--disk', type=int, default=100000, help='Number of disk for the job')
    parser.add_argument('-T', '--time', type=int, default=86400, help='Time limit for the job in seconds (default: 86400, max: 345600)')
    parser.add_argument('-w', '--dry-run', action='store_true', help='Perform a dry run without submitting jobs')
    parser.add_argument('-d', '--output-dir', type=str, help='Output directory for job files')
    parser.add_argument('--transfer-files', type=str, default="yes", help='Should transfer files (default: yes)')
    parser.add_argument('--output', type=str, default="job_$(Cluster)_$(Process).out", help='Output file (default: job_$(Cluster)_$(Process).out)')
    parser.add_argument('--error', type=str, default="job_$(Cluster)_$(Process).err", help='Error file (default: job_$(Cluster)_$(Process).err)')
    parser.add_argument('--log', type=str, default="job_$(Cluster)_$(Process).log", help='Log file (default: job_$(Cluster)_$(Process).log)')
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
    max_time = 345600  # 4 days in seconds
    if args.time > max_time:
        logging.error(f"Time limit cannot exceed {max_time} seconds")
        exit(1)
    
    table = [
        ["Command",  "Parameter",                     "Value"],
        ["-f",      f"{R}Input file{RE}",             f"{R}{args.input}{RE}"],
        ["-n",      f"{R}Number of jobs{RE}",         f"{R}{args.njobs}{RE}"],
        ["-c",      f"{M}Custom executable{RE}",      f"{M}{args.custom_exe}{RE}"],
        ["-q",      f"{C}Queue{RE}",                  f"{C}{args.queue}{RE}"],
        ["-m",      f"{C}Memory{RE}",                 f"{C}{args.mem}{RE}"],
        ["-t",      f"{C}Number of cpus per job{RE}", f"{C}{args.ncpu}{RE}"],
        ["-o",      f"{C}Number of disk (kB){RE}",    f"{C}{args.disk}{RE}"],
        ["-T",      f"{C}Time limit{RE}",             f"{C}{args.time}{RE}"],
        ["auto",       f"{B}FLUKA Path{RE}",             f"{B}{FLUKA_PATH}{RE}"],
        ["auto",       f"{B}FLUKA Folder{RE}",           f"{B}{FLUKA_FOLDER}{RE}"],
        ["-d",      f"{B}Output Directory{RE}",       f"{B}{args.output_dir if args.output_dir else 'Default'}{RE}"],
        ["-w",      f"{Y}Dry Run{RE}",                f"{Y}{args.dry_run}{RE}"],
        ["--transfer-files",       f"{Y}Transfer Files{RE}",         f"{Y}{args.transfer_files}{RE}"],
        ["--output",       f"{Y}Output File{RE}",            f"{Y}{args.output}{RE}"],
        ["--error",       f"{Y}Error File{RE}",             f"{Y}{args.error}{RE}"],
        ["--log",       f"{Y}Log File{RE}",               f"{Y}{args.log}{RE}"]
    ]
    print(tabulate(table, headers="firstrow", tablefmt="simple_outline"))

    confirmation = input("Proceed with launching jobs? (yes/no): ")
    if confirmation.lower() not in ['yes', 'y']:
        logging.info(f"{R}Aborting job launch.{RE}")
        exit()

    launch_jobs(args.input, args.njobs, args.custom_exe, args.queue, args.mem, args.ncpu, args.disk, args.time, args.dry_run, args.output_dir, args.transfer_files, args.output, args.error, args.log)
