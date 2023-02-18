import torch


class Model(torch.nn.Module):
    def __init__(self, path_to_weights="Models/EmbeddingVAE/embedding_vae.pt", bottleneck_size=128, device="cpu"):
        super().__init__()
        self.bottleneck_size = bottleneck_size
        self.encoder = Encoder(bottleneck_size=self.bottleneck_size)
        self.decoder = Decoder(bottleneck_size=self.bottleneck_size)
        self.prior_distribution = torch.distributions.Normal(0, 1)
        self.device = device
        if path_to_weights is not None:
            self.load_state_dict(torch.load(path_to_weights, map_location="cpu")["model"])
        self.to(device)

    def forward(self,
                target_data=None,  # during training this should be a batch of target data.
                # During inference simply leave this out to sample unconditionally.
                noise_scale_during_inference=0.8,
                z=None):
        if target_data is not None:
            # run the encoder
            means, variance = self.encoder(target_data)
            variance = variance.exp()  # so that our model learns to predict in log space, which has more room to work with

            # convert means and variance to latent sample
            z = means + variance * self.prior_distribution.sample(means.shape).to(self.device)

        else:
            if z is None:
                z = torch.randn(self.bottleneck_size).to(self.device).unsqueeze(0) * noise_scale_during_inference

        # run the decoder
        reconstructions_of_targets = self.decoder(z)

        if target_data is not None:
            # calculate the losses
            predicted_distribution = torch.distributions.Normal(means, variance)
            kl_loss = torch.distributions.kl_divergence(predicted_distribution, self.prior_distribution).mean()
            reconstruction_loss = torch.nn.functional.mse_loss(reconstructions_of_targets, target_data,
                                                               reduction="mean")
            return reconstructions_of_targets, kl_loss, reconstruction_loss

        return reconstructions_of_targets


class Encoder(torch.nn.Module):
    def __init__(self, bottleneck_size):
        """
        takes in a 256 dimensional speaker embedding and bottlenecks the information into a compressed vector
        """
        super().__init__()
        self.nn = torch.nn.Sequential(
            torch.nn.Linear(256, 256),
            torch.nn.Tanh(),
            torch.nn.Linear(256, 256),
            torch.nn.Tanh(),
            torch.nn.Linear(256, 128),
            torch.nn.Tanh(),
            torch.nn.Linear(128, 128),
            torch.nn.Tanh(),
            torch.nn.Linear(128, bottleneck_size),
            torch.nn.Tanh()
        )
        self.proj_mean = torch.nn.Sequential(
            torch.nn.Linear(bottleneck_size, bottleneck_size),
            torch.nn.Tanh(),
            torch.nn.Linear(bottleneck_size, bottleneck_size),
            torch.nn.ReLU(),
        )
        self.proj_var = torch.nn.Sequential(
            torch.nn.Linear(bottleneck_size, bottleneck_size),
            torch.nn.Tanh(),
            torch.nn.Linear(bottleneck_size, bottleneck_size),
            torch.nn.ReLU(),
        )

    def forward(self, target_data_for_compression):
        compressed = self.nn(target_data_for_compression)
        return self.proj_mean(compressed), self.proj_var(compressed)


class Decoder(torch.nn.Module):
    def __init__(self, bottleneck_size):
        """
        takes in a compressed vector and decompresses it into a 256 dimensional speaker embedding
        """
        super().__init__()
        self.nn = torch.nn.Sequential(
            torch.nn.Linear(bottleneck_size, 128),
            torch.nn.Tanh(),
            torch.nn.Linear(128, 128),
            torch.nn.Tanh(),
            torch.nn.Linear(128, 128),
            torch.nn.Tanh(),
            torch.nn.Linear(128, 256),
            torch.nn.Tanh(),
            torch.nn.Linear(256, 256),
            torch.nn.Tanh(),
            torch.nn.Linear(256, 256)
        )

    def forward(self, compressed_data_for_decompression):
        decompressed = self.nn(compressed_data_for_decompression)
        return decompressed