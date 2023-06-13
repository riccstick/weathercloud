#! /usr/bin/python3

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import glob

DIR = '/home/ricci/weathercloud/'

def read_and_sample_csv(file_path, num_points_to_plot):
    df = pd.read_csv(file_path, encoding='utf-16-le', sep=';', header=0, thousands='.', decimal=',', skip_blank_lines=True, on_bad_lines='skip')
    sampled_df = df.sample(n=num_points_to_plot, replace=False)
    return sampled_df

num_points_to_plot = 1600
combined_df = pd.DataFrame()

csv_files = glob.glob(DIR + 'data/*.csv')  # Update the path to your CSV files

for file in csv_files:
    sampled_data = read_and_sample_csv(file, num_points_to_plot)
    combined_df = pd.concat([combined_df, sampled_data])

x_column_index = 0  # Update with the desired column index for the x-axis data
# 2 -> Temperature außen
# 9 -> Luftfeuchtigkeit außen 
# 11 -> Durch. Windgeschwindigkeit
# 14 -> Regen
# 15 -> Regenrate
# 16 -> Solarstrahlung
y_column_index = 2

x_axis_column_name=sampled_data.columns[0]
y_axis_column_name=sampled_data.columns[y_column_index]

combined_df[x_axis_column_name] = pd.to_datetime(combined_df[x_axis_column_name], format='%Y-%m-%d %H:%M:%S', errors='coerce')
combined_df = combined_df.sort_values(x_axis_column_name)

x_values = combined_df.iloc[:, x_column_index]
y_values = combined_df.iloc[:, y_column_index]

# Compute moving averages
window_size = 100
combined_df['moving_average'] = combined_df[y_axis_column_name].rolling(window_size).mean()

# Plot the data and moving averages
plt.figure(figsize=(10240/300, 3840/300), dpi=300)
plt.grid(True, linestyle='--', linewidth=0.5, color='gray', alpha=0.5)
plt.plot(combined_df[x_axis_column_name], combined_df[y_axis_column_name], label='Measured Data', ms = 0, linestyle = '-', lw = 1.5, color = '#C0C0C0')
plt.plot(combined_df[x_axis_column_name], combined_df['moving_average'], label='Moving Average', ms = 1, color = 'red', marker = '.', linestyle = '')
plt.xticks(fontsize=15)
plt.yticks(fontsize=15)
plt.xlabel(x_axis_column_name, fontsize=16)
plt.ylabel(y_axis_column_name, fontsize=16)
plt.title('Wetterdaten Langau 124, 2091 Langau, NÖ: ' + y_axis_column_name, fontsize=18)
plt.legend(fontsize=14)
plt.savefig(DIR + '/' + y_axis_column_name + '.png', format='png', dpi=300)
#plt.show()

