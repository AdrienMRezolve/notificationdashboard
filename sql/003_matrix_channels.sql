-- Surface the Matrix-bridged channels in the dashboard. The notifications
-- channel check already allows 'whatsapp' and 'linkedin'; these rows just make
-- them show up in the sidebar with health status fed by the ingester.

insert into connections (channel) values ('whatsapp'), ('linkedin')
on conflict (channel) do nothing;
