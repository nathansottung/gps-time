"""analysis-tower-delay-check: measured against predicted tower delays, from a marker-timed capture.

Reads an observation file (SigMF + gpstime:, time_source pps_marker) and the predictions of
reference-broadcast-towers; finds each tower's known waveform in the samples; compares the
measured delay with the predicted one. Synthetic data only so far.
"""
