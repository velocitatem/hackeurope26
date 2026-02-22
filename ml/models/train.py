import torch
import torch.nn as nn
from torch.utils.tensorboard import SummaryWriter

from lib import get_logger

logger = get_logger("ml-trainloop")


class Trainer:
    def __init__(self, model, train_loader, log_dir="../tensorboard", device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = model.to(self.device)
        self.train_loader = train_loader
        self.optimizer = torch.optim.Adam(model.parameters())
        self.criterion = nn.CrossEntropyLoss()
        self.writer = SummaryWriter(log_dir)
        self.step = 0
        logger.info("training initialized device=%s", self.device)

    def train_epoch(self) -> float:
        self.model.train()
        total_loss = 0.0
        batch_count = 0
        for batch_idx, (data, target) in enumerate(self.train_loader):
            data = data.to(self.device)
            target = target.to(self.device)
            self.optimizer.zero_grad()
            output = self.model(data)
            loss = self.criterion(output, target)
            loss.backward()
            self.optimizer.step()

            total_loss += float(loss.item())
            batch_count += 1

            if batch_idx % 100 == 0:
                self.writer.add_scalar("Loss/Train", loss.item(), self.step)
                self.step += 1
        if batch_count == 0:
            return 0.0
        return total_loss / batch_count

    def train(self, epochs):
        for epoch in range(epochs):
            avg_loss = self.train_epoch()
            logger.info("epoch=%d avg_loss=%.6f", epoch + 1, avg_loss)
        self.writer.close()
