function plot_all(configPath)
% Plot only checked numerical MAT outputs. Never generate replacement waveforms.
cfg=jsondecode(fileread(configPath));
if ~exist(cfg.output_dir,'dir'), mkdir(cfg.output_dir); end
for fi=1:numel(cfg.figures)
    spec=cfg.figures(fi);
    data=load(spec.data);
    fig=figure('Visible','off','Color','w','Position',[100 100 850 220*numel(spec.panels)]);
    guard=onCleanup(@()close(fig));
    tiledlayout(numel(spec.panels),1,'TileSpacing','compact','Padding','compact');
    for pi=1:numel(spec.panels)
        panel=spec.panels(pi); nexttile; hold on;
        xcol='t'; if isfield(panel,'x_column'), xcol=panel.x_column; end
        xx=data.(xcol); assert(isvector(xx) && all(isfinite(xx(:))) && all(diff(xx(:))>0),'Invalid axis');
        if isfield(panel,'kind') && strcmp(panel.kind,'heatmap')
            yy=data.(panel.y_column); zz=data.(panel.z_column);
            assert(isequal(size(zz),[numel(xx),numel(yy)]) && all(isfinite(zz(:))),'Heatmap axis/shape mismatch');
            imagesc(xx(:)*panel.x_factor,yy(:)*panel.y_factor,zz.'); set(gca,'YDir','normal'); colorbar;
            xlabel(panel.xlabel); ylabel(panel.ylabel);
            if isfield(panel,'clim'), clim(panel.clim); end
            continue;
        end
        for ci=1:numel(panel.columns)
            if iscell(panel.columns), col=panel.columns{ci}; else, col=panel.columns(ci); end
            yy=data.(col); assert(isreal(yy) && numel(yy)==numel(xx) && all(isfinite(yy(:))),'Invalid data column');
            plot(xx(:)*panel.x_factor,yy(:)*panel.y_factor,'LineWidth',1.2);
        end
        xlabel(panel.xlabel); ylabel(panel.ylabel);
        if isfield(panel,'labels'), legend(panel.labels,'Interpreter','none','Location','best'); end
        if isfield(panel,'xlim'), xlim(panel.xlim); end
        if isfield(panel,'ylim'), ylim(panel.ylim); end
        if isfield(panel,'xscale'), set(gca,'XScale',panel.xscale); end
        if isfield(panel,'yscale'), set(gca,'YScale',panel.yscale); end
        set(gca,'FontName','Arial','FontSize',10,'Box','on');
    end
    base=fullfile(cfg.output_dir,spec.id);
    exportgraphics(fig,[base '.png'],'Resolution',300);
    exportgraphics(fig,[base '.pdf'],'ContentType','vector');
    savefig(fig,[base '.fig']);
    print(fig,[base '.svg'],'-dsvg');
    clear guard;
end
end
