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

        def apply_template(template_applier, template_name, **kwargs):
            bindings = ncs.template.Variables()
            for key, value in kwargs.items():
                bindings.add(key, value)
            self.log.info(f"Applying template '{template_name}' with bindings {bindings}")
            template_applier.apply(template_name, bindings)

        self.log.info('Service create(service=', service._path, ')')
        applier = ncs.template.Template(service)

        for pe in service.provider_edge_devices.pe:
            # pe.device, .router_id, .isis_net_entity, .label, .rd, .core_connections
            self.log.info(f'Connecting device {pe.device}')
            for core_connection in pe.core_connections:
                # core_connection.connected_pe, .interface, .ipv4-address, .ipv4-prefixlen
                remote_pe = service.provider_edge_devices.pe[core_connection.connected_pe]
                # remote_pe.device, .router_id, .isis_net_entity, .label, .rd, .core_connections
                self.log.info(f'Connected to remote pe {remote_pe.device}')
                for edge_connection in pe.edge_connections:
                    apply_template(applier, 'evpn-template', 
                        DEVICE = pe.device, 
                        AS = service.evpn__as,
                        RD = pe.rd,
                        LABEL = pe.label,
                        ISIS_NET_ENTITY = pe.isis_net_entity,
                        SOURCE_ADDRESS = pe.router_id,
                        DESTINATION_ADDRESS = remote_pe.router_id,
                        CORE_INTERFACE = core_connection.interface,
                        CORE_ADDRESS = core_connection.ipv4_address,
                        CORE_MASK = prefixlen2mask(core_connection.ipv4_prefixlen),
                        EDGE_INTERFACE = edge_connection.interface,
                        EDGE_INTERFACE_TYPE = interface_type(edge_connection.interface),
                        EDGE_SUBINTERFACE = edge_connection.subinterface,
                    )
        self.log.info('Service create done')

class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING')
        self.register_service('evpn-servicepoint', ServiceCallbacks)

    def teardown(self):
        self.log.info('Main FINISHED')
