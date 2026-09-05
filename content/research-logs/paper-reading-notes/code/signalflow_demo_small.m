%% Minimal reproducibility demo for the iEC signal-flow hierarchy method
% This demo intentionally uses the processed MMP-360 resting-state iEC
% distributed with the authors' repository. It tests the hierarchy-estimation
% stage without downloading the large HCP/PRIME-DE raw datasets.

clear; close all; clc;
root = fileparts(mfilename('fullpath'));
addpath(genpath(root));

dataFile = fullfile(root, 'data', 'MMP360_resting_iEC.mat');
refFile  = fullfile(root, 'data', 'MMP360_resting_hierarchy.mat');
outDir   = fullfile(root, 'demo_results');
if ~exist(outDir, 'dir'); mkdir(outDir); end

S = load(dataFile);
if isfield(S, 'iEC_vfl')
    iEC = S.iEC_vfl;
elseif isfield(S, 'iEC')
    iEC = S.iEC;
else
    error('No iEC matrix found in %s', dataFile);
end

% The paper/repository uses proportional thresholding at 15% of the
% strongest absolute directed edges for the hierarchy estimate.
threshold = 0.15;
hierarchy = computeHierarchyLevels(iEC, threshold);

% The repository includes the authors'' saved hierarchy map. This is a
% reproducibility check of the supplied implementation and data, not an
% independent biological validation.
R = load(refFile);
reference = R.hierarchyLevels;
% Use base-MATLAB arithmetic here so the demo does not require the
% Statistics and Machine Learning Toolbox just to compute a correlation.
hv = hierarchy(:); rv = reference(:);
hv = hv - mean(hv); rv = rv - mean(rv);
rho = (hv' * rv) / sqrt((hv' * hv) * (rv' * rv));
rmse = sqrt(mean((hierarchy(:) - reference(:)).^2, 'omitnan'));

% Basic signed-flow summaries.
positiveOut = sum(max(iEC, 0), 1)';
negativeOut = sum(max(-iEC, 0), 1)';

fprintf('iEC size: %d x %d\n', size(iEC,1), size(iEC,2));
fprintf('Threshold: top %.0f%% absolute edges\n', threshold*100);
fprintf('Hierarchy vs repository reference: r = %.6f, RMSE = %.6f\n', rho, rmse);
fprintf('Positive/negative absolute outflow ratio: %.4f\n', ...
    sum(positiveOut) / max(sum(negativeOut), eps));

save(fullfile(outDir, 'demo_results.mat'), 'iEC', 'hierarchy', 'reference', ...
    'positiveOut', 'negativeOut', 'threshold', 'rho', 'rmse');

% Lightweight visualization that works without cortical surface toolboxes.
f = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 1100 420]);
tiledlayout(1, 3, 'Padding', 'compact', 'TileSpacing', 'compact');
nexttile; imagesc(iEC); axis image off; colorbar;
title('Provided MMP-360 iEC');
nexttile; plot(hierarchy, 'k.', 'MarkerSize', 8); hold on;
plot(reference, 'r-', 'LineWidth', 1); grid on;
xlabel('Parcel'); ylabel('Hierarchy level');
title(sprintf('Hierarchy check: r=%.3f', rho));
legend({'Recomputed', 'Repository'}, 'Location', 'best');
nexttile; scatter(positiveOut, hierarchy, 10, 'filled'); grid on;
xlabel('Positive outgoing flow'); ylabel('Hierarchy level');
title('Signed flow sanity check');
exportgraphics(f, fullfile(outDir, 'demo_summary.png'), 'Resolution', 180);
close(f);

fprintf('Saved results to: %s\n', outDir);
