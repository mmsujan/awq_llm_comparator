import argparse
import numpy as np 
import os
from os import listdir
import errno
import sys
from run_llm_io_binding import llm_params
from run_llm_io_binding import llm_main

SUCCESS = 0
ERROR = 1
UNKNOWN_FAILURE = 2

#Levenshtein gives minimum distance to make two string same using Insertion, Deletion and Substitution operations
#The algorithm can work in Character or word level
#Comparision is not case sensitive

def levenshtien_distance(source, target):
    len_s = len(source)
    len_t = len(target)
    
    #create matrix to store the distances between substring
    matrix = [[0]*(len_t+1) for _ in range(len_s+1)]
    
    for i in range(len_s+1):
        matrix[i][0] = i
    for j in range(len_t+1):
        matrix[0][j] = j
        
    for i in range(1, len_s+1):
        for j in range(1, len_t+1):
            substitutionCost  = 0 if source[i-1].lower() == target[j-1].lower() else 1
            matrix[i][j] = min(matrix[i-1][j] + 1, #Deletion
                matrix[i][j-1] + 1, #insertion
                matrix[i-1][j-1] + substitutionCost ) #substitution
    return matrix[len_s][len_t]

def compare(model_type, threshold, compare_mode, platform, verbosity):
    
    file1_path = "./goldenOutput/" + model_type + "/output.txt"
    file2_path = "./generatedOutput/" + model_type + "/output.txt"
    
    if not os.path.isfile(file2_path) or not os.path.isfile(file1_path):
        if verbosity:
         raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file2_path)
         sys.exit(1)
        return UNKNOWN_FAILURE
    with open(file1_path, 'r') as file1:
        content1 = None
        if compare_mode == "Word":
            content1 = file1.read().split()
        elif compare_mode == "Character":
            content1 = file1.read()
        else:
            content1 = file1.readlines()
            #content1 = file1.read().split()
    with open(file2_path, 'r') as file2:
        content2 = None 
        if compare_mode == "Word":
            content2 = file2.read().split()
        elif compare_mode == "Character":
            content2 = file2.read()
        else:
            content2 = file2.readlines()
            #content2 = file2.read().split()
    
    mismatch_count = 0
    err_code = SUCCESS
    
    
    if (compare_mode == "Word" or compare_mode == "Character"):
        
        
        distance = levenshtien_distance(content1, content2)
        if distance > threshold:
            err_code = ERROR
            if verbosity:
                print("Mismatch count between golden and generated output is more than threshold: mismatch count = ", distance, " threshold = ", threshold)
        return err_code
    
    
    non_empty_lines_1 = [line for line in content1 if line.strip()]
    non_empty_lines_2 = [line for line in content2 if line.strip()]
    #Todo need add logic when golden and generated outputs are not same
    for i, (item1, item2) in enumerate(zip(non_empty_lines_1, non_empty_lines_2)):
        item1_words = item1.split()
        item2_words = item2.split()
        for j, (w1, w2) in enumerate(zip(item1_words, item2_words)):
            if w1 != w2:
                mismatch_count += 1
                if verbosity:
                    print ( w1, " != ", w2)
        # when 2 lines are not equal
        mismatch_count = mismatch_count + abs(len(item2_words) - len(item1_words))

    if mismatch_count > threshold:
        err_code = ERROR
        if verbosity:
            print("Mismatch count = ", mismatch_count, " and threshold = ", threshold)
    
    return err_code
    
    
    
def run_comparator(model_type, threshold, compare_mode, platform, verbosity):
    
    #compare generated image with golden image
    print("Comparing generated text with golden text...")
    ret_code = compare(model_type, threshold, compare_mode, platform, verbosity)
    print("code : ", ret_code)
    if verbosity:
        if ret_code == SUCCESS:
            print("PASS!")
        elif ret_code == ERROR:
            print("ERROR!")
        else:
            print("Unknown Failure!")   
    return ret_code
    
def add_text_compare_params(parser):
    parser.add_argument("--threshold", default= 5, type=int, help="Maximum number of difference between generated and golden text.")
    parser.add_argument("--compare_mode", default="Line", type=str, help="Compare mode : Character, Word or Line")
    parser.add_argument("--platform", default="DG2", type=str, help="Platform: DG2")
    parser.add_argument("--verbosity", action="store_true", help="Print error details")
## main function for other script    
def main():
    parser = argparse.ArgumentParser()
    text_com_group = parser.add_argument_group(title="text comparator params")
    llm_group = parser.add_argument_group(title="llm params")
    add_text_compare_params(text_com_group)
    llm_params(llm_group)
    args = parser.parse_args()
    #create image using stable diffusion 
    llm_main(args);
    
    return run_comparator(args.model_type, args.threshold, args.compare_mode, args.platform, args.verbosity)
    
if __name__ == "__main__":
   main()
