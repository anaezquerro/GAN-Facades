import torch.nn as nn
import torchvision.models as models

# Code extracted from: https://github.com/pochih/FCN-pytorch/tree/master

ranges = {
    "vgg11": ((0, 3), (3, 6), (6, 11), (11, 16), (16, 21)),
    "vgg13": ((0, 5), (5, 10), (10, 15), (15, 20), (20, 25)),
    "vgg16": ((0, 5), (5, 10), (10, 17), (17, 24), (24, 31)),
    "vgg19": ((0, 5), (5, 10), (10, 19), (19, 28), (28, 37)),
}

# cropped version from https://github.com/pytorch/vision/blob/master/torchvision/models/vgg.py
cfg = {
    "vgg11": [64, "M", 128, "M", 256, 256, "M", 512, 512, "M", 512, 512, "M"],
    "vgg13": [64, 64, "M", 128, 128, "M", 256, 256, "M", 512, 512, "M", 512, 512, "M"],
    "vgg16": [
        64,
        64,
        "M",
        128,
        128,
        "M",
        256,
        256,
        256,
        "M",
        512,
        512,
        512,
        "M",
        512,
        512,
        512,
        "M",
    ],
    "vgg19": [
        64,
        64,
        "M",
        128,
        128,
        "M",
        256,
        256,
        256,
        256,
        "M",
        512,
        512,
        512,
        512,
        "M",
        512,
        512,
        512,
        512,
        "M",
    ],
}


def make_layers(cfg, batch_norm=False):
    layers = []
    in_channels = 3
    for v in cfg:
        if v == "M":
            layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
        else:
            conv2d = nn.Conv2d(in_channels, v, kernel_size=3, padding=1)
            if batch_norm:
                layers += [conv2d, nn.BatchNorm2d(v), nn.ReLU(inplace=True)]
            else:
                layers += [conv2d, nn.ReLU(inplace=True)]
            in_channels = v
    return nn.Sequential(*layers)


class VGGNet(models.VGG):
    def __init__(
        self,
        pretrained=True,
        model="vgg16",
        requires_grad=True,
        remove_fc=True,
        show_params=False,
    ):
        super().__init__(make_layers(cfg[model]))
        self.ranges = ranges[model]

        if pretrained:
            exec(
                "self.load_state_dict(models.%s(pretrained=True).state_dict())" % model
            )

        if not requires_grad:
            for param in super().parameters():
                param.requires_grad = False

        if remove_fc:  # delete redundant fully-connected layer params, can save memory
            del self.classifier

        if show_params:
            for name, param in self.named_parameters():
                print(name, param.size())

    def forward(self, x):
        output = {}

        # get the output of each maxpooling layer (5 maxpool in VGG net)
        for idx in range(len(self.ranges)):
            for layer in range(self.ranges[idx][0], self.ranges[idx][1]):
                x = self.features[layer](x)
            output["x%d" % (idx + 1)] = x

        return output


class FCN8s(nn.Module):
    def __init__(self, num_classes, pretrained_net):
        super().__init__()

        # Load pre-trained model
        self.backbone = pretrained_net

        self.relu = nn.LeakyReLU(0.5, inplace=True)
        self.conv1 = nn.ConvTranspose2d(
            512, 512, kernel_size=3, stride=2, padding=1, dilation=1, output_padding=1
        )
        self.bn1 = nn.BatchNorm2d(512)
        self.conv2 = nn.ConvTranspose2d(
            512, 256, kernel_size=3, stride=2, padding=1, dilation=1, output_padding=1
        )
        self.bn2 = nn.BatchNorm2d(256)
        self.conv3 = nn.ConvTranspose2d(
            256, 128, kernel_size=3, stride=2, padding=1, dilation=1, output_padding=1
        )
        self.bn3 = nn.BatchNorm2d(128)
        self.conv4 = nn.ConvTranspose2d(
            128, 64, kernel_size=3, stride=2, padding=1, dilation=1, output_padding=1
        )
        self.bn4 = nn.BatchNorm2d(64)
        self.conv5 = nn.ConvTranspose2d(
            64, 32, kernel_size=3, stride=2, padding=1, dilation=1, output_padding=1
        )
        self.bn5 = nn.BatchNorm2d(32)
        self.classifier = nn.Conv2d(32, num_classes, kernel_size=1)
        self.act = nn.Tanh()

    def forward(self, x):
        # Backbone
        x = self.backbone(x)

        x5 = x["x5"]  # size=(N, 512, x.H/32, x.W/32)
        x4 = x["x4"]  # size=(N, 512, x.H/16, x.W/16)
        x3 = x["x3"]  # size=(N, 256, x.H/8,  x.W/8)

        x = self.relu(self.conv1(x5))
        x = self.bn1(x + x4)
        x = self.relu(self.conv2(x))
        x = self.bn2(x + x3)
        x = self.bn3(self.relu(self.conv3(x)))
        x = self.bn4(self.relu(self.conv4(x)))
        x = self.bn5(self.relu(self.conv5(x)))
        x = self.classifier(x)

        return self.act(x)
