# jetskulls

## 简介
基于容器ubuntu桌面和docker镜像（快照）的无限试用jetbrains IDE的方案。

## 使用方法
* 环境：x86或x64/linux/docker/python/pip
* 执行`./init.sh`进行初始化，产生`jetskulls`执行文件
* 执行`./jetskulls build IDE类型`构建ide初始快照，如`./jetskulls build goland`，初始快照名固定为v0
* 通过`./jetskulls IDE类型 start 参数 v0`，从初始快照中启动IDE，详细参数见命令说明
* 访问http://IP:6080，执行桌面上提供的sh脚本，打开对应IDE，进行初始化配置，安装所需的IDE插件，以及必要的软件工具（如git、编译器等）
* 确认配置好后，执行`./jetskulls IDE类型 snapshot 快照名`保存快照，如`./jetskulls goland snapshot v1`
* 此时可继续使用IDE。后续也可在任意时间（如30天试用到期后）执行`./jetskulls IDE类型 start 快照名`来恢复对应的快照

## 特殊说明
* start不指定web参数时，默认使用6080端口
* start可以额外指定vnc协议的端口，以便通过vnc-viewer直接访问桌面，默认不开启vnc协议端口
* start可以指定挂载参数，从而将linux宿主机目录挂载到IDE虚拟环境内（如源代码目录）。不指定时，默认挂载当前工作目录里的src目录下对应的IDE类型的子目录
* start可以指定登录密码，不指定时将不会提示登陆信息。若指定密码，登录用户名为<b>root</b>
* 可自行定义IDE类型，仿照goland.json新增对应配置后即可按上述命令扩展使用
* linux宿主机不需要桌面，桌面功能由docker镜像提供

## 使用示例
* `./jetskulls build goland`，构建goland首个快照
* `./jetskulls goland ls`，查看goland快照列表
* `./jetskulls goland ps`，查看goland IDE是否正在运行
* `./jetskulls goland snapshot jetbrains`，给正在运行的goland IDE产生一个名为jetbrains的快照
* `./jetskulls goland start --web-password 123 jetbrains`指定密码，从jetbrains快照中启动IDE，此时IDE桌面可以看到src源码目录，对应到宿主机当前工作目录下的src/goland/目录
* `./jetskulls goland start --web-port 6081 --vnc-port 5901 --mount /home:/home,/var/log/messages:/var/log/messages jetbrains`分别指定端口和挂载目录，从jetbrains快照中启动IDE
* `./jetskulls goland stop`，停止goland IDE
