# jetskulls

## 简介
基于容器ubuntu桌面和docker镜像的无限试用jetbrains IDE的方案。

## 使用方法
* 环境：linux/docker/python/pip
* 执行`./init.sh`进行初始化，产生`jetskulls`执行文件
* 执行`./jetskulls build IDE类型`构建第一个ide快照，如`./jetskulls build goland`，第一个快照名固定为v0
* 通过`./jetskulls IDE类型 start 参数 v0`，从第一个快照中启动IDE
* 访问http://IP:6080，执行桌面上提供的sh脚本，打开对应IDE，进行初始化配置，安装所需的插件
* 确认配置好后，执行`./jetskulls IDE类型 snapshot 快照名`保存快照，如`./jetskulls goland snapshot v1`
* 此时可继续使用IDE。后续也可在任意时间（如30天试用到期后）执行`./jetskulls IDE类型 start 快照名`来恢复对应的快照

## 特殊说明
* start不指定web参数时，默认使用6080端口
* start可以额外指定vnc协议的端口，以便通过vnc-viewer直接访问桌面，默认不开启vnc协议端口
* start需要指定挂载参数，从而将linux宿主机目录挂载到IDE虚拟环境内（如源代码目录）
* 可自行定议IDE类型，仿照goland.json新增对应配置后即可按上述命令扩展使用
* linux宿主机不需要桌面，桌面功能由docker镜像提供

## 使用示例
* `./jetskulls build goland`，构建goland首个快照
* `./jetskulls goland ls`，查看goland快照列表
* `./jetskulls goland ps`，查看goland IDE是否正在运行
* `./jetskulls goland snapshot jetbrains`，给正在运行的goland IDE产生一个名为jetbrains的快照
* `./jetskulls goland start --web-port 6081 --vnc-port 5901 --mount /home:/home,/var/log/messages:/var/log/messages jetbrains`分别指定端口和挂载目录，从jetbrains快照中启动IDE
* `./jetskulls goland stop`，停止goland IDE
