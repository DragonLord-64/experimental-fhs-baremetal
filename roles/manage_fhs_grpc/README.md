# Manage FHS gRPC
Manages the [gRPC](https://grpc.io/docs/languages/python/quickstart/) controller services for VCC/FSP, allowing them to be deployed on target hosts, configured, and shut down as required.

## External References

- [VCC gRPC controller repository](https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-vcc-grpc-controller)
- [FSP gRPC controller repository](https://gitlab.com/ska-telescope/ska-mid-cbf/host-software/ska-mid-cbf-fhs-fsp-grpc-controller)

## Requirements

The gRPC controllers use Poetry to manage dependencies. If running on a fresh installation, run the Poetry installation playbook to ensure they can be set up correctly. Currently, usage of Poetry requires that access to PyPi be maintained.

Also requires that compressed tarballs for the controllers be provided. Currently, custom `pyproject.toml` files for both should also be provided, to get around errors due to sources for packages being changed.

Additionally, the gRPC controllers that bitstream sources be provided.

## Variables

*All variables are prefixed with manage_grpc_*

| **Variable Name**    | **Use**                                                                                                                                                      | **Default/Example** |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|
| grpc_fsp_controller  | Defines the version of the FSP gRPC controller to install. Must have `S<VERSION>.tar.gz` present in the files directory.. | ska-mid-cbf-fhs-fsp-grpc-controller-0.0.3               |
| grpc_vcc_controller  | Defines the version of the VCC gRPC controller to install. Must have `<VERSION>.tar.gz` present in the files directory.  | ska-mid-cbf-fhs-vcc-grpc-controller-0.0.3               |
| grpc_vcc_bitstream   | Bitstream tarball to use for VCC. Must have `<VERSION>.tar.gz` present in the files directory.                                               | ska-mid-cbf-bitstreams-1.2.0               |
| grpc_fsp_bitstream   | Bitstream tarball to use for VCC. Must have `<VERSION>.tar.gz` present in the files directory.                                          | ska-mid-cbf-fsp-corr-bitstreams-0.1.0               |
| grpc_grpcurl_version | The version of the .deb image of gRPCurl provided in the files directory.                                                                                    | grpcurl_1.9.3_linux_amd64               |
| grpc_port            | Port to use for the gRPC service.                                                                                                                            | 50051               |
| grpc_emulation_mode  | Set to true if emulation mode should be used.                                                                                                                | true                |
| card                 | ID of the FPGA card to connect to with gRPC.                                                                                                                 | t1413c1             |
| device_address       | The PCIe bus device addresses to gain access to the registers.                                                                                               | 0000:81:00.1        |
| device_region        | PCIe BAR connected to the memory mapped registers                                                                                                            | 0                   |

## Tags/Usage

## grpc_install

Extracts and deploys provided tarballs (via version number defined) for VCC/FSP to the target system(s), and installs them into the FHS virtual env via Poetry. Also installs the required bitstreams from the provided bitstream tarballs. Once these setup stages are complete, uploads and restarts the .service file for both controllers, running them as background processes. These can be verified by running `journalctl -u vcc-grpc.service` and `journalctl -u fsp-grpc.service` and verifying that the GRPC server starts on each.

## grpcurl_install

Installs [gRPCurl](https://github.com/fullstorydev/grpcurl) onto the target system, allowing local polling of the VCC/FSP endpoints. Requires the debian image be provided under `/files`.

## grpc_configure

Uploads and restarts the service files for he gRPC controllers. Use if updating the commands to execute the gRPC controllers.

## grpcurl_poll

Runs a basic polling command against gRPCurl to validate that the vcc target is working. Polls the base driver and prints the output from the request.