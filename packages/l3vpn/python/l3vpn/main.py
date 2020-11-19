# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service

class ServiceCallbacks(Service):
    @Service.create
    def cb_create(self, tctx, root, service, proplist):

        def prefixlen2mask(prefixlen):
            masks = {
                24: "255.255.255.0", 32: "255.255.255.255"
            }
            return masks[prefixlen]

        def interface_type(interface):
            for interface_type in ["GigabitEthernet", "25GE"]:
                if interface_type in interface:
                    return interface_type
            return "Unknown"

        def allocate_rd(device_name):
            return { 
                "hw1": "4",
                "hwx4": "5",
            }[device_name]

        def allocate_label(device_name):
            return { 
                "hw1": "100",
                "hwx4": "200",
            }[device_name]

        def allocate_subif(edge_interface):
            return { 
                "GigabitEthernet0/1/9": "4",
                "25GE3/0/70": "4",
            }[edge_interface]

        def edge_interface_lookup(device_name):
            return { 
                "hw1": "GigabitEthernet0/1/9",
                "hwx4": "25GE3/0/70",
            }[device_name]

        def apply_template(template_applier, template_name, **kwargs):
            bindings = ncs.template.Variables()
            for key, value in kwargs.items():
                bindings.add(key, value)
            self.log.info(f"Applying template '{template_name}' with bindings {bindings}")
            template_applier.apply(template_name, bindings)

        self.log.info('Service create(service=', service._path, ')')
        applier = ncs.template.Template(service)

        for sna in service.site_network_accesses.site_network_access:
            # sna.device_reference .ip_connection .service .vpn_attachment
            self.log.info(f'Processing site_network_access {sna.site_network_access_id}')
            pe_topo = root.topo[sna.vpn_attachment.vpn_id, sna.device_reference]
            # pe_topo.vpn_name .device_name .connected_to_device .router_id .isis_net_entity .interface .core_address .core_prefixlen
            remote_topo = root.topo[sna.vpn_attachment.vpn_id, pe_topo.connected_to_device]
            self.log.info(f'Configuring pe device {pe_topo.device_name}')
            edge_interface = edge_interface_lookup(pe_topo.device_name)
            apply_template(applier, 'l3vpn-template', 
                DEVICE = pe_topo.device_name,
                AS = sna.vpn_attachment.vpn_id,
                RD = allocate_rd(pe_topo.device_name),
                LABEL = allocate_label(pe_topo.device_name),
                ISIS_NET_ENTITY = pe_topo.isis_net_entity,
                SOURCE_ADDRESS = pe_topo.router_id,
                DESTINATION_ADDRESS = remote_topo.router_id,
                CORE_INTERFACE = pe_topo.interface,
                CORE_ADDRESS = pe_topo.core_address,
                CORE_MASK = prefixlen2mask(pe_topo.core_prefixlen),
                EDGE_INTERFACE = edge_interface,
                EDGE_INTERFACE_TYPE = interface_type(edge_interface),
                EDGE_SUBINTERFACE = allocate_subif(edge_interface),
                EDGE_ADDRESS = sna.ip_connection.ipv4.addresses.provider_address,
                EDGE_MASK = prefixlen2mask(sna.ip_connection.ipv4.addresses.prefix_length),
                EDGE_ADDRESS_IPV6 = sna.ip_connection.ipv6.addresses.provider_address,
                EDGE_PREFIXLEN_IPV6 = sna.ip_connection.ipv4.addresses.prefix_length,
            )
        self.log.info('Service create done')

class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING')
        self.register_service('l3vpn-servicepoint', ServiceCallbacks)

    def teardown(self):
        self.log.info('Main FINISHED')
