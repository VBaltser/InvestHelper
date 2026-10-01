# frozen_string_literal: true

VAGRANTFILE_API_VERSION = "2"

VM_CONFIG = {
  "jenkins" => {
    hostname: "jenkins",
    ip: "192.168.56.10",
    cpus: 2,
    memory: 4096
  },
  "app" => {
    hostname: "app",
    ip: "192.168.56.20",
    cpus: 2,
    memory: 4096
  }
}.freeze

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.box_check_update = true

  # Ansible will configure the machines over SSH, so a shared project folder
  # is unnecessary and the setup does not depend on VirtualBox Guest Additions.
  config.vm.synced_folder ".", "/vagrant", disabled: true

  VM_CONFIG.each do |name, vm|
    config.vm.define name do |machine|
      machine.vm.hostname = vm[:hostname]
      machine.vm.network "private_network", ip: vm[:ip]

      machine.vm.provider "virtualbox" do |virtualbox|
        virtualbox.name = "investhelper-#{name}"
        virtualbox.gui = false
        virtualbox.cpus = vm[:cpus]
        virtualbox.memory = vm[:memory]
      end

      machine.vm.provision "shell", privileged: true, inline: <<-SHELL
        set -eu

        if ! grep -q "192.168.56.10 jenkins" /etc/hosts; then
          echo "192.168.56.10 jenkins" >> /etc/hosts
        fi

        if ! grep -q "192.168.56.20 app" /etc/hosts; then
          echo "192.168.56.20 app" >> /etc/hosts
        fi

        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y \
          ca-certificates \
          curl \
          python3 \
          python3-apt
      SHELL
    end
  end
end
